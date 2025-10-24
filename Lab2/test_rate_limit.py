import socket
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
import sys
from queue import Queue
import logging

# Configure logging to show timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class RateLimitedTester:
    """Tests HTTP server performance with rate-limited concurrent requests."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def _send_single_request(self, request_id: int, resource: str) -> Tuple[int, float, bool, str, float]:
        """
        Sends a single HTTP GET request and returns (request_id, time_taken, success, status_code, end_time).
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

            # Extract status code from response
            response = b''.join(chunks).decode("utf-8", errors="ignore")
            status_code = "UNKNOWN"
            if response:
                first_line = response.split('\n')[0]
                parts = first_line.split(' ')
                if len(parts) >= 2:
                    status_code = parts[1]

            elapsed = time.time() - start_time
            end_time = time.time()
            return request_id, elapsed, True, status_code, end_time
        except Exception as e:
            elapsed = time.time() - start_time
            end_time = time.time()
            return request_id, elapsed, False, "ERROR", end_time

    def test_rate_limited_requests(
        self,
        resource: str = "",
        num_requests: int = 10,
        rate: float = 10.0,
        num_workers: int = 1,
    ) -> Tuple[float, int]:
        """
        Makes rate-limited requests to the server and measures performance.

        Args:
            resource: The resource path to request (default: root)
            num_requests: Total number of requests to send
            rate: Request rate in requests per second (default: 10.0)
            num_workers: Number of worker threads (default: 1)

        Returns:
            Tuple of (total_time, successful_requests)
        """
        print(f"\n{'='*70}")
        print(
            f"Testing {num_requests} rate-limited requests to http://{self.host}:{self.port}/{resource}"
        )
        print(f"Rate: {rate:.2f} requests/second")
        print(f"Workers: {num_workers}")
        print(f"{'='*70}\n")

        interval = 1.0 / rate  # Time between request submissions
        times: List[float] = []
        successful_requests = 0
        results = {}  # Dictionary to store results by request_id

        # Record the overall start time
        overall_start = time.time()

        def rate_limited_submitter(executor):
            """Submit requests at the specified rate."""
            for i in range(num_requests):
                # Submit the request
                future = executor.submit(
                    self._send_single_request, i + 1, resource)
                results[i + 1] = future

                # Sleep to maintain rate (except after last request)
                if i < num_requests - 1:
                    time.sleep(interval)

        # Use ThreadPoolExecutor to handle concurrent requests
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Start a thread to submit requests at the specified rate
            submission_thread = threading.Thread(
                target=rate_limited_submitter, args=(executor,), daemon=False
            )
            submission_thread.start()

            # Wait for submission thread to finish submitting all requests
            submission_thread.join()

            # Collect and display results as they complete
            for future in as_completed(results.values()):
                request_id, elapsed, success, status_code, end_time = future.result()
                times.append(elapsed)
                if success and status_code == '200':
                    successful_requests += 1

                # Format timestamp with milliseconds
                from datetime import datetime
                timestamp = datetime.fromtimestamp(
                    end_time).strftime('%H:%M:%S.%f')[:-3]
                status_symbol = '✓' if success and status_code == '200' else '✗'
                print(
                    f"Request {request_id:2d}: {timestamp} - took {elapsed:.3f}s, status: {status_code} - {status_symbol}"
                )

        overall_elapsed = time.time() - overall_start

        # Print statistics
        print(f"\n{'-'*70}")
        print("STATISTICS:")
        print(f"{'-'*70}")
        print(f"Successful requests: {successful_requests}/{num_requests}")
        print(f"Total time (wall-clock): {overall_elapsed:.3f}s")
        if times:
            print(f"Average request time: {sum(times) / len(times):.3f}s")
            print(f"Min request time: {min(times):.3f}s")
            print(f"Max request time: {max(times):.3f}s")
        print(
            f"Actual throughput: {num_requests / overall_elapsed:.2f} requests/second"
        )
        print(f"Intended rate: {rate:.2f} requests/second")
        print(f"{'-'*70}\n")

        return overall_elapsed, successful_requests


def main():
    """Main function to run rate-limited tests."""
    if len(sys.argv) < 3:
        print(
            "Usage: python test_rate_limit.py <host> <port> [resource] [num_requests] [rate] [num_workers]"
        )
        print("Example: python test_rate_limit.py localhost 8080 '' 100 10.0")
        print("Example: python test_rate_limit.py localhost 8080 'api' 50 5.0 3")
        print("\nParameters:")
        print("  host: Server hostname or IP")
        print("  port: Server port")
        print("  resource: Resource path (default: '')")
        print("  num_requests: Total number of requests (default: 10)")
        print("  rate: Requests per second (default: 10.0)")
        print("  num_workers: Number of worker threads (default: 1)")
        sys.exit(1)

    host = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except ValueError:
        print(
            f"Error: Port must be an integer, got '{sys.argv[2]}'", file=sys.stderr
        )
        sys.exit(1)

    resource = sys.argv[3] if len(sys.argv) > 3 else ""

    try:
        num_requests = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    except ValueError:
        print(
            f"Error: num_requests must be an integer, got '{sys.argv[4]}'", file=sys.stderr
        )
        sys.exit(1)

    try:
        rate = float(sys.argv[5]) if len(sys.argv) > 5 else 10.0
    except ValueError:
        print(
            f"Error: Rate must be a number, got '{sys.argv[5]}'", file=sys.stderr
        )
        sys.exit(1)

    try:
        num_workers = int(sys.argv[6]) if len(sys.argv) > 6 else 1
    except ValueError:
        print(
            f"Error: num_workers must be an integer, got '{sys.argv[6]}'", file=sys.stderr
        )
        sys.exit(1)

    tester = RateLimitedTester(host, port)
    overall_time, successful = tester.test_rate_limited_requests(
        resource=resource,
        num_requests=num_requests,
        rate=rate,
        num_workers=num_workers,
    )

    # Return exit code based on success
    sys.exit(0 if successful == num_requests else 1)


if __name__ == "__main__":
    main()
