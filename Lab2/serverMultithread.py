import socket
import sys
import mimetypes
import urllib.parse
import threading
import time
from pathlib import Path
from http import HTTPStatus
from typing import Optional, Tuple
from collections import defaultdict, deque

# counter
request_counts = defaultdict(int)  # path -> number of requests
counts_lock = threading.Lock()

# rate limiting feature
rate_limits = defaultdict(deque)   # ip -> timestamps of recent requests
rate_lock = threading.Lock()

# configs
RATE_LIMIT = 5
WORK_DELAY = 1.0  # in seconds


def extract_client_identifier(request_data: str, socket_addr: tuple) -> str:
    """Extract client IP for rate limiting (IP only, no port)"""

    # try X-Forwarded-For from nginx
    for line in request_data.splitlines():
        if line.lower().startswith("x-forwarded-for:"):
            client_ip = line.split(":",
                                   1)[1].strip().split(",")[0].strip()
            print(f"[CLIENT ID] X-Forwarded-For: {client_ip}",
                  file=sys.stderr)
            return client_ip

    # direct connection - use socket IP only
    client_ip = socket_addr[0]
    print(f"[CLIENT ID] Direct connection: {client_ip}", file=sys.stderr)
    return client_ip


def check_rate_limit(ip: str) -> bool:
    """Checks if an IP has exceeded the rate limit. Thread-safe."""
    now = time.monotonic()
    with rate_lock:
        q = rate_limits[ip]
        # remove entries older than 1 second
        while q and now - q[0] > 1:
            q.popleft()

        if len(q) >= RATE_LIMIT:
            return False
        # Add current request timestamp
        q.append(now)
        return True


class ThreadedHttpServer:
    """
    A multi-threaded HTTP server that serves files, directory listings,
    tracks hit counts, and enforces rate limiting.
    """

    def __init__(self, host: str, port: int, base_dir: str):
        self.host = host
        self.port = port
        self.base_dir = Path(base_dir).resolve()
        self.server_socket = None
        self._running = False

    def run(self) -> None:
        # start  server
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(
            f"Serving directory '{self.base_dir}' on http://{self.host}:{self.port}")

        self._running = True
        while self._running:
            try:
                conn, addr = self.server_socket.accept()
                print(f"Accepted connection from {addr}")
                # create thread
                thread = threading.Thread(
                    target=self._handle_request, args=(conn, addr))
                thread.daemon = True
                thread.start()
            except KeyboardInterrupt:
                self.stop()
            except OSError:
                break
        print("\nServer has been shut down.")

    def stop(self) -> None:
        """Stops the server."""
        self._running = False
        if self.server_socket:
            # сreate a dummy connection to unblock .accept()
            try:
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
                    (self.host, self.port))
            except ConnectionRefusedError:
                pass
            self.server_socket.close()

    def _parse_request(self, conn: socket.socket) -> Optional[Tuple[str, str, str]]:
        # This method remains the same
        try:
            request_data = conn.recv(2048).decode("utf-8")
            if not request_data:
                return None
            request_line = request_data.splitlines()[0]
            method, path, _ = request_line.split()
            return method, path, request_data
        except (ValueError, IndexError, UnicodeDecodeError):
            return None

    def _handle_request(self, conn: socket.socket, addr: tuple) -> None:
        try:
            parsed_request = self._parse_request(conn)
            if not parsed_request:
                self._send_error(conn, HTTPStatus.BAD_REQUEST)
                return

            method, path, request_data = parsed_request

            # Extract unique client identifier for rate limiting
            client_id = extract_client_identifier(request_data, addr)

            # use the unique client identifier to check rate limit
            if not check_rate_limit(client_id):
                self._send_error(conn, HTTPStatus.TOO_MANY_REQUESTS)
                return

            if method != "GET":
                self._send_error(conn, HTTPStatus.METHOD_NOT_ALLOWED)
                return

            time.sleep(WORK_DELAY)

            relative_path = urllib.parse.unquote(path.lstrip('/'))
            requested_path = (self.base_dir / relative_path).resolve()

            # path traversal check
            if not requested_path.is_relative_to(self.base_dir):
                raise PermissionError("Path traversal attempt.")

            # the "fixed" version using a lock.
            with counts_lock:
                request_counts[str(requested_path)] += 1

            # for demonstration, this is the "naive" racy version:
            # old_value = request_counts.get(str(requested_path), 0)
            # time.sleep(0.001)  # force a context switch
            # request_counts[str(requested_path)] = old_value + 1

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
            try:
                self._send_error(conn, HTTPStatus.INTERNAL_SERVER_ERROR)
            except Exception as se:
                print(f"Failed to send error response: {se}", file=sys.stderr)
        finally:
            conn.close()  # ensure the connection is closed for this thread

    def _serve_file(self, conn: socket.socket, file_path: Path) -> None:
        """Serves a single file by streaming it in chunks (from original script)."""
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

        # stream the file body in chunks (efficient)
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(4096)  # read 4KB at a time
                if not chunk:
                    break
                try:
                    conn.sendall(chunk)
                except socket.error:
                    break

    def _serve_directory(self, conn: socket.socket, dir_path: Path, url_path: str) -> None:
        """Serves a directory listing as an HTML table with hit counts."""
        if not url_path.endswith('/'):
            url_path += '/'

        html_body_str = f"""
        <html>
        <head>
            <style>
                body {{ background-color: #333; color: #eee; font-family: sans-serif; }}
                table {{ border-collapse: collapse; margin-top: 1em; width: 60%; }}
                th, td {{ border: 1px solid #777; padding: 0.5em; }}
                th {{ background-color: #555; text-align: left; }}
                a {{ color: #9cf; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
            <title>Directory listing for {url_path}</title>
        </head>
        <body>
            <h2>Directory listing for {url_path}</h2>
            <table>
                <tr><th>File / Directory</th><th>Hits</th></tr>
        """

        items_html = []

        if url_path != "/":
            items_html.append(
                '<tr><td><a href="..">.. (Parent Directory)</a></td><td>-</td></tr>')

        for item in sorted(list(dir_path.iterdir())):
            href = urllib.parse.quote(item.name)
            display_name = item.name
            full_path_str = str(item.resolve())

            with counts_lock:
                count = request_counts.get(full_path_str, 0)

            if item.is_dir():
                items_html.append(
                    f'<tr><td><a href="{href}/">{display_name}/</a></td><td>{count}</td></tr>')
            else:
                items_html.append(
                    f'<tr><td><a href="{href}">{display_name}</a></td><td>{count}</td></tr>')

                # finish table
        html_body_str += "".join(items_html)
        html_body_str += "</table></body></html>"
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
        body_str = (f"<html><head><title>{status.value} {status.phrase}</title></head>"
                    f"<body><h1>{status.value} {status.phrase}</h1>")
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            body_str += f"<p>Rate limit exceeded. Please try again later.</p>"
        body_str += "</body></html>"
        body = body_str.encode("utf-8")

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

    server = ThreadedHttpServer("0.0.0.0", port, base_dir)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()


if __name__ == "__main__":
    main()
