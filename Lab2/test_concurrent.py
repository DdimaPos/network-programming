#!/usr/bin/env python3

import socket
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple
import sys


class ConcurrentTester:
    """Tests HTTP server performance with concurrent requests."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _send_single_request(self, resource: str) -> Tuple[float, bool]:
        """
        Sends a single HTTP GET request and returns (time_taken, success).
        """
        start_time = time.time()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                request = f"GET /{resource} HTTP/1.1\r\nHost: {self.host}\r\nConnection: close\r\n\r\n"
                s.sendall(request.encode("utf-8"))

                # Receive the full response
                chunks = []
                while True:
                    data = s.recv(4096)
                    if not data:
                        break
                    chunks.append(data)

            elapsed = time.time() - start_time
            return elapsed, True
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"Error requesting {resource}: {e}", file=sys.stderr)
            return elapsed, False

    def test_concurrent_requests(
        self, resource: str = "", num_requests: int = 10, num_workers: int = 10
    ) -> None:
        """
        Makes concurrent requests to the server and measures performance.

        Args:
            resource: The resource path to request (default: root)
            num_requests: Number of concurrent requests
            num_workers: Number of worker threads (default: same as num_requests)
        """
        print(f"\n{'='*70}")
        print(
            f"Testing {num_requests} concurrent requests to http://{self.host}:{self.port}/{resource}")
        print(f"{'='*70}\n")

        times: List[float] = []
        successful_requests = 0

        # Record the overall start time
        overall_start = time.time()

        # Use ThreadPoolExecutor to handle concurrent requests
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all requests
            futures = [
                executor.submit(self._send_single_request, resource)
                for _ in range(num_requests)
            ]

            # Collect results as they complete
            for i, future in enumerate(as_completed(futures), 1):
                elapsed, success = future.result()
                times.append(elapsed)
                if success:
                    successful_requests += 1
                print(
                    f"Request {i:2d}: {elapsed:.3f}s - {'✓' if success else '✗'}")

        overall_elapsed = time.time() - overall_start

        # Print statistics
        print(f"\n{'-'*70}")
        print("STATISTICS:")
        print(f"{'-'*70}")
        print(f"Successful requests: {successful_requests}/{num_requests}")
        print(f"Total time (wall-clock): {overall_elapsed:.3f}s")
        print(f"Average request time: {sum(times) / len(times):.3f}s")
        print(f"Min request time: {min(times):.3f}s")
        print(f"Max request time: {max(times):.3f}s")
        print(
            f"Throughput: {num_requests / overall_elapsed:.2f} requests/second")
        print(f"{'-'*70}\n")

        return overall_elapsed, successful_requests


def main():
    """Main function to run concurrent tests."""
    if len(sys.argv) < 3:
        print(
            "Usage: python test_concurrent.py <host> <port> [resource] [num_requests]")
        print("Example: python test_concurrent.py localhost 8080 '' 10")
        print("Example: python test_concurrent.py localhost 8080 'images' 20")
        sys.exit(1)

    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except ValueError:
        print(
            f"Error: Port must be an integer, got '{sys.argv[2]}'", file=sys.stderr)
        sys.exit(1)

    resource = sys.argv[3] if len(sys.argv) > 3 else ""
    num_requests = int(sys.argv[4]) if len(sys.argv) > 4 else 10

    tester = ConcurrentTester(host, port)
    overall_time, successful = tester.test_concurrent_requests(
        resource=resource, num_requests=num_requests
    )

    # Return exit code based on success
    sys.exit(0 if successful == num_requests else 1)


if __name__ == "__main__":
    main()
