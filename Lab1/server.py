import socket
import sys
import mimetypes
import urllib.parse
from pathlib import Path
from http import HTTPStatus
from typing import Optional, Tuple


class SynchronousStreamServer:
    """
    A synchronous, single-client HTTP server that uses file streaming.
    It handles one request at a time but can serve large files efficiently.
    """

    def __init__(self, host: str, port: int, base_dir: str):
        self.host = host
        self.port = port
        self.base_dir = Path(base_dir).resolve()
        self.server_socket = None
        self._running = False

    def run(self) -> None:
        """Starts the server and handles connections sequentially."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        print(
            f"Serving directory '{self.base_dir}' on http://{self.host}:{self.port}")

        self._running = True
        while self._running:
            try:
                conn, addr = self.server_socket.accept()
                # Use a 'with' statement to ensure the connection is closed
                with conn:
                    print(f"Accepted connection from {addr}")
                    # Handle the request directly in the main thread
                    self._handle_request(conn)
            except KeyboardInterrupt:
                self.stop()
            except OSError:
                break  # Socket was closed

        print("\nServer has been shut down.")

    def stop(self) -> None:
        """Stops the server."""
        self._running = False
        if self.server_socket:
            self.server_socket.close()

    def _parse_request(self, conn: socket.socket) -> Optional[Tuple[str, str]]:
        # This method remains the same
        try:
            request_data = conn.recv(2048).decode("utf-8")
            if not request_data:
                return None
            request_line = request_data.splitlines()[0]
            method, path, _ = request_line.split()
            return method, path
        except (ValueError, IndexError):
            return None

    def _handle_request(self, conn: socket.socket) -> None:
        """Handles a single client connection sequentially."""
        try:
            parsed_request = self._parse_request(conn)
            if not parsed_request:
                self._send_error(conn, HTTPStatus.BAD_REQUEST)
                return

            method, path = parsed_request
            if method != "GET":
                self._send_error(conn, HTTPStatus.METHOD_NOT_ALLOWED)
                return

            relative_path = urllib.parse.unquote(path.lstrip('/'))
            requested_path = (self.base_dir / relative_path).resolve()

            if not requested_path.is_relative_to(self.base_dir):
                raise PermissionError("Path traversal attempt.")

            if requested_path.is_dir():
                self._serve_directory(conn, requested_path, path)
            elif requested_path.is_file():
                self._serve_file(conn, requested_path)
            else:
                self._send_error(conn, HTTPStatus.NOT_FOUND)
        except (PermissionError, FileNotFoundError):
            self._send_error(conn, HTTPStatus.NOT_FOUND)
        except Exception as e:
            print(f"Error handling request: {e}", file=sys.stderr)
            self._send_error(conn, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _serve_file(self, conn: socket.socket, file_path: Path) -> None:
        """Serves a single file by streaming it in chunks (OPTIMIZATION RETAINED)."""
        mime_type, _ = mimetypes.guess_type(file_path) or (
            "application/octet-stream", None)
        file_size = file_path.stat().st_size

        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size),
            "Connection": "close"
        }
        header_bytes = self._build_header_block(HTTPStatus.OK, headers)
        conn.sendall(header_bytes)

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                conn.sendall(chunk)

    def _serve_directory(self, conn: socket.socket, dir_path: Path, url_path: str) -> None:
        # This method remains the same
        if not url_path.endswith('/'):
            url_path += '/'
        items_html = []
        if url_path != "/":
            items_html.append(
                f'<li><a href="..">.. (Parent Directory)</a></li>')

        for item in sorted(list(dir_path.iterdir())):
            href, display_name = urllib.parse.quote(item.name), item.name
            if item.is_dir():
                items_html.append(
                    f'<li>[DIR] <a href="{href}/">{display_name}/</a></li>')
            else:
                items_html.append(
                    f'<li><a href="{href}">{display_name}</a></li>')

        html_body_str = f'<html><head><title>Index of {url_path}</title></head>' \
                        f'<body><h2>Index of {url_path}</h2><ul>{"".join(items_html)}</ul></body></html>'
        body = html_body_str.encode("utf-8")

        headers = {"Content-Type": "text/html; charset=UTF-8",
                   "Content-Length": str(len(body))}
        response = self._build_response(HTTPStatus.OK, headers, body)
        conn.sendall(response)

    def _build_header_block(self, status: HTTPStatus, headers: dict) -> bytes:
        # This method remains the same
        status_line = f"HTTP/1.1 {status.value} {status.phrase}"
        header_lines = [status_line] + \
            [f"{key}: {value}" for key, value in headers.items()]
        return ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8")

    def _build_response(self, status: HTTPStatus, headers: dict, body: bytes = b"") -> bytes:
        # This method remains the same
        headers.setdefault("Connection", "close")
        header_block = self._build_header_block(status, headers)
        return header_block + body

    def _send_error(self, conn: socket.socket, status: HTTPStatus) -> None:
        # This method remains the same
        body = f"<html><body><h1>{status.value} {status.phrase}</h1></body></html>".encode(
            "utf-8")
        headers = {"Content-Type": "text/html; charset=UTF-8",
                   "Content-Length": str(len(body))}
        response = self._build_response(status, headers, body)
        conn.sendall(response)


def main():
    if len(sys.argv) < 2 or not Path(sys.argv[1]).is_dir():
        print(
            f"Usage: python {sys.argv[0]} <directory> [port]", file=sys.stderr)
        sys.exit(1)

    base_dir = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

    server = SynchronousStreamServer("0.0.0.0", port, base_dir)
    server.run()


if __name__ == "__main__":
    main()
