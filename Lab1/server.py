import socket
import sys
import mimetypes
import urllib.parse
import logging
from pathlib import Path
from http import HTTPStatus
from typing import Optional, Tuple


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)


class SynchronousStreamServer:
    """
    A synchronous, single-client HTTP server that uses file streaming and logging.
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
        logging.info(
            f"Serving directory '{self.base_dir}' on http://{self.host}:{self.port}")

        self._running = True
        while self._running:
            try:
                conn, addr = self.server_socket.accept()
                with conn:
                    self._handle_request(conn, addr)
            except KeyboardInterrupt:
                self.stop()
            except OSError:
                break  # Socket was closed

        logging.info("Server has been shut down.")

    def stop(self) -> None:
        """Stops the server."""
        self._running = False
        if self.server_socket:
            self.server_socket.close()

    def _parse_request(self, conn: socket.socket) -> Optional[Tuple[str, str]]:
        try:
            request_data = conn.recv(2048).decode("utf-8")
            if not request_data:
                return None
            request_line = request_data.splitlines()[0]
            method, path, _ = request_line.split()
            return method, path
        except (ValueError, IndexError):
            return None

    def _handle_request(self, conn: socket.socket, addr: tuple) -> None:
        """Handles a single client connection sequentially."""
        try:
            parsed_request = self._parse_request(conn)
            if not parsed_request:
                logging.warning(
                    f"Received malformed/empty request from {addr}")
                self._send_error(conn, HTTPStatus.BAD_REQUEST, addr)
                return

            method, path = parsed_request
            logging.info(f"Request from {addr}: {method} {path}")

            if method != "GET":
                self._send_error(conn, HTTPStatus.METHOD_NOT_ALLOWED, addr)
                return

            relative_path = urllib.parse.unquote(path.lstrip('/'))
            requested_path = (self.base_dir / relative_path).resolve()

            if not requested_path.is_relative_to(self.base_dir):
                raise PermissionError("Path traversal attempt.")

            if requested_path.is_dir():
                self._serve_directory(conn, requested_path, path, addr)
            elif requested_path.is_file():
                self._serve_file(conn, requested_path, addr)
            else:
                raise FileNotFoundError("Resource not found.")
        except (PermissionError, FileNotFoundError) as e:
            logging.warning(f"Failed request from {addr}: {e}")
            self._send_error(conn, HTTPStatus.NOT_FOUND, addr)
        except Exception as e:
            logging.error(
                f"Internal error handling request from {addr}: {e}", exc_info=True)
            self._send_error(conn, HTTPStatus.INTERNAL_SERVER_ERROR, addr)

    def _serve_file(self, conn: socket.socket, file_path: Path, addr: tuple) -> None:
        """Serves a single file by streaming it in chunks."""
        mime_type, _ = mimetypes.guess_type(file_path) or (
            "application/octet-stream", None)
        file_size = file_path.stat().st_size

        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size),
            "Connection": "close"
        }

        logging.info(f"Sending response to {addr}: 200 OK ({mime_type})")
        header_bytes = self._build_header_block(HTTPStatus.OK, headers)
        conn.sendall(header_bytes)

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                conn.sendall(chunk)

    def _serve_directory(self, conn: socket.socket, dir_path: Path, url_path: str, addr: tuple) -> None:
        """Serves a directory listing."""
        if not url_path.endswith('/'):
            url_path += '/'
        items_html = []
        if url_path != "/":
            items_html.append(f'<li><a href="..">..</a></li>')

        for item in sorted(list(dir_path.iterdir())):
            href, display_name = urllib.parse.quote(item.name), item.name
            if item.is_dir():
                items_html.append(
                    f'<li><a href="{href}/">{display_name}/</a></li>')
            else:
                items_html.append(
                    f'<li><a href="{href}">{display_name}</a></li>')

        html_body_str = f'<html><head><title>Index of {url_path}</title></head>' \
                        f'<body><h2>Index of {url_path}</h2><ul>{"".join(items_html)}</ul></body></html>'
        body = html_body_str.encode("utf-8")

        headers = {"Content-Type": "text/html; charset=UTF-8",
                   "Content-Length": str(len(body))}

        logging.info(f"Sending response to {addr}: 200 OK (text/html)")
        response = self._build_response(HTTPStatus.OK, headers, body)
        conn.sendall(response)

    def _build_header_block(self, status: HTTPStatus, headers: dict) -> bytes:
        status_line = f"HTTP/1.1 {status.value} {status.phrase}"
        header_lines = [status_line] + \
            [f"{key}: {value}" for key, value in headers.items()]
        return ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8")

    def _build_response(self, status: HTTPStatus, headers: dict, body: bytes = b"") -> bytes:
        headers.setdefault("Connection", "close")
        header_block = self._build_header_block(status, headers)
        return header_block + body

    def _send_error(self, conn: socket.socket, status: HTTPStatus, addr: tuple) -> None:
        """Sends a standard HTTP error response."""
        logging.info(
            f"Sending response to {addr}: {status.value} {status.phrase}")
        body = f"<html><body><h1>{status.value} {status.phrase}</h1></body></html>".encode(
            "utf-8")
        headers = {"Content-Type": "text/html; charset=UTF-8",
                   "Content-Length": str(len(body))}
        response = self._build_response(status, headers, body)
        conn.sendall(response)


def main():
    if len(sys.argv) < 2 or not Path(sys.argv[1]).is_dir():
        logging.error(f"Usage: python {sys.argv[0]} <directory> [port]")
        logging.error("Please provide a valid directory to serve.")
        sys.exit(1)

    base_dir = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

    server = SynchronousStreamServer("0.0.0.0", port, base_dir)
    server.run()


if __name__ == "__main__":
    main()
