import socket
import sys
from pathlib import Path
from typing import Dict, Tuple, Optional


class SimpleHttpClient:
    """A simple HTTP client to send GET requests and handle responses."""

    def _save_file(self, directory: Path, filename: str, content: bytes) -> None:
        """Saves binary content to a file in the specified directory."""
        directory.mkdir(parents=True, exist_ok=True)
        filepath = directory / filename
        filepath.write_bytes(content)
        print(f"✅ Saved file: {filepath} ({len(content)} bytes)")

    def _parse_response(self, response: bytes) -> Tuple[str, Dict[str, str], bytes]:
        """Splits an HTTP response into status line, headers, and body."""
        try:
            header_data, body = response.split(b"\r\n\r\n", 1)
        except ValueError:
            return "", {}, response

        header_lines = header_data.decode(
            "utf-8", errors="ignore").split("\r\n")
        status_line = header_lines[0] if header_lines else ""

        headers = {}
        for line in header_lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        return status_line, headers, body

    def _send_request(self, host: str, port: int, resource: str) -> Optional[bytes]:
        """Sends an HTTP GET request and returns the full response."""
        # Sanitize resource path to ensure it doesn't start with a slash
        resource = resource.lstrip('/')
        request = f"GET /{resource} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                s.sendall(request.encode("utf-8"))

                chunks = []
                while True:
                    data = s.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
            return b"".join(chunks)

        except (socket.gaierror, ConnectionRefusedError, socket.timeout) as e:
            print(
                f"❌ Error: Connection to {host}:{port} failed. {e}", file=sys.stderr)
            return None

    def fetch(self, host: str, port: int, resource: str, save_dir: str) -> None:
        """
        Fetches a resource and acts based on its content type:
        - HTML: Prints the body to the console.
        - PNG/PDF: Saves the file to the specified directory.
        """
        response = self._send_request(host, port, resource)
        if response is None:
            return

        status_line, headers, body = self._parse_response(response)

        print("=== Response Headers ===")
        print(status_line)
        for key, value in headers.items():
            print(f"{key.title()}: {value}")
        print("=========================\n")

        content_type = headers.get("content-type", "").lower()

        if "text/html" in content_type:
            print("--- HTML Content Received ---")
            print(body.decode("utf-8", errors="ignore"))
            print("---------------------------")
        elif "image/png" in content_type or "application/pdf" in content_type:
            filename = Path(resource).name
            # If the resource path is empty (e.g., '/'), create a default name
            if not filename:
                ext = "png" if "png" in content_type else "pdf"
                filename = f"downloaded_file.{ext}"
            self._save_file(Path(save_dir), filename, body)
        else:
            print(
                f"ℹ️ Received content of type '{content_type}'. No specific action defined.")
            print("Displaying raw body as a fallback:")
            try:
                print(body.decode('utf-8', errors='replace'))
            except Exception:
                print(f"<Could not decode {len(body)} bytes of binary data>")


def main():
    """Main function to parse command-line arguments and run the client."""
    if len(sys.argv) != 5:
        print(
            f"Usage: python {sys.argv[0]} <server_host> <server_port> <url_path> <directory>")
        print(
            f"Example: python {sys.argv[0]} localhost 8080 images/photo.png downloaded_files")
        sys.exit(1)

    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except ValueError:
        print(
            f"❌ Error: Port must be an integer, but got '{sys.argv[2]}'.", file=sys.stderr)
        sys.exit(1)

    resource = sys.argv[3]
    save_directory = sys.argv[4]

    client = SimpleHttpClient()
    client.fetch(host, port, resource, save_directory)


if __name__ == "__main__":
    main()
