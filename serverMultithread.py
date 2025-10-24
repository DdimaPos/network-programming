import socket
import sys
import mimetypes
import urllib.parse
import threading
from pathlib import Path
from http import HTTPStatus
from typing import Optional, Tuple


class ThreadedHttpServer:
    """
    A multi-threaded HTTP server that serves files and directory listings from scratch.
    It handles multiple connections concurrently and streams large files efficiently.
    """

    def __init__(self, host: str, port: int, base_dir: str):
        self.host = host
        self.port = port
        self.base_dir = Path(base_dir).resolve()
        self.server_socket = None
        self._running = False

    def run(self) -> None:
        """Starts the server and spawns a new thread for each connection."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)  # Listen for up to 5 queued connections
        print(
            f"Serving directory '{self.base_dir}' on http://{self.host}:{self.port}")

        self._running = True
        while self._running:
            try:
                conn, addr = self.server_socket.accept()
                print(f"Accepted connection from {addr}")
                # Create and start a new thread to handle the client request
                thread = threading.Thread(
                    target=self._handle_request, args=(conn,))
                thread.daemon = True  # Allows main thread to exit even if workers are running
                thread.start()
            except KeyboardInterrupt:
                self.stop()
            except OSError:
                # This can happen when the socket is closed while accept() is blocking
                break

        print("\nServer has been shut down.")

    def stop(self) -> None:
        """Stops the server."""
        self._running = False
        if self.server_socket:
            self.server_socket.close()

    def _parse_request(self, conn: socket.socket) -> Optional[Tuple[str, str]]:
        # This method remains the same as before
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
        """Handles a single client connection within a dedicated thread."""
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
            print(f"Error in handler thread: {e}", file=sys.stderr)
            self._send_error(conn, HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            conn.close()  # Ensure the connection is closed for this thread

    def _serve_file(self, conn: socket.socket, file_path: Path) -> None:
        """Serves a single file by streaming it in chunks."""
        mime_type, _ = mimetypes.guess_type(file_path) or (
            "application/octet-stream", None)
        file_size = file_path.stat().st_size

        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size),
            "Connection": "close"
        }
        # Send the headers first
        header_bytes = self._build_header_block(HTTPStatus.OK, headers)
        conn.sendall(header_bytes)

        # Now, stream the file body in chunks
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)  # Read 4KB at a time
                if not chunk:
                    break  # End of file
                conn.sendall(chunk)

    def _serve_directory(self, conn: socket.socket, dir_path: Path, url_path: str) -> None:
        # This method remains mostly the same, but uses the response builder
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
                    f'<li>DIRECTORY/ <a href="{href}/">{display_name}/</a></li><br>')
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
        """Constructs just the header part of an HTTP response."""
        status_line = f"HTTP/1.1 {status.value} {status.phrase}"
        header_lines = [status_line] + \
            [f"{key}: {value}" for key, value in headers.items()]
        return ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8")

    def _build_response(self, status: HTTPStatus, headers: dict, body: bytes = b"") -> bytes:
        """Constructs a full HTTP response with a body."""
        headers.setdefault("Connection", "close")
        header_block = self._build_header_block(status, headers)
        return header_block + body

    def _send_error(self, conn: socket.socket, status: HTTPStatus) -> None:
        """Sends a standard HTTP error response."""
        body = f"<html><body><h1>{status.value} {status.phrase}</h1></body></html>".encode(
            "utf-8")
        headers = {"Content-Type": "text/html; charset=UTF-8",
                   "Content-Length": str(len(body))}
        response = self._build_response(status, headers, body)
        conn.sendall(response)


def main():
    # Main function is identical, but now runs the ThreadedHttpServer
    if len(sys.argv) < 2 or not Path(sys.argv[1]).is_dir():
        print(
            f"Usage: python {sys.argv[0]} <directory> [port]", file=sys.stderr)
        sys.exit(1)

    base_dir = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

    server = ThreadedHttpServer("0.0.0.0", port, base_dir)
    server.run()


if __name__ == "__main__":
    main()
