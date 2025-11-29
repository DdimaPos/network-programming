import requests
import time
import statistics
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor

LEADER_URL = "http://localhost:8001"
FOLLOWER_URLS = [
    "http://localhost:8002", "http://localhost:8003",
    "http://localhost:8004", "http://localhost:8005", "http://localhost:8006"
]


def set_quorum(n):
    requests.post(f"{LEADER_URL}/config", json={"quorum": n})


def write_operation(key, value):
    start = time.time()
    try:
        resp = requests.post(f"{LEADER_URL}/write",
                             json={"key": key, "value": value})
        resp.raise_for_status()
        duration = (time.time() - start) * 1000  # ms
        return duration
    except Exception as e:
        print(f"Error: {e}")
        return None


def run_benchmark(quorum_size, total_writes=100, concurrency=10):
    print(f"--- Testing Quorum: {quorum_size} ---")
    set_quorum(quorum_size)

    keys = [f"key_{i}" for i in range(10)]

    latencies = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for i in range(total_writes):
            k = keys[i % 10]
            v = f"val_{i}"
            futures.append(executor.submit(write_operation, k, v))

        for f in futures:
            res = f.result()
            if res is not None:
                latencies.append(res)

    avg_latency = statistics.mean(latencies)
    print(f"Average Latency: {avg_latency:.4f} ms")
    return avg_latency


def clear_all_stores():
    """Clear data from leader and all followers."""
    print("Clearing all stores...")

    # Clear leader
    try:
        resp = requests.delete(f"{LEADER_URL}/clear")
        resp.raise_for_status()
        print("  Leader cleared")
    except Exception as e:
        print(f"  Failed to clear leader: {e}")

    # Clear all followers
    for i, f_url in enumerate(FOLLOWER_URLS):
        try:
            resp = requests.delete(f"{f_url}/clear")
            resp.raise_for_status()
            print(f"  Follower {i+1} cleared")
        except Exception as e:
            print(f"  Failed to clear follower {i+1}: {e}")


def check_consistency():
    print("\n--- Checking Consistency ---")
    leader_data = requests.get(f"{LEADER_URL}/read_all").json()

    print(f"Leader has {len(leader_data)} keys")

    all_match = True
    for i, f_url in enumerate(FOLLOWER_URLS):
        try:
            f_data = requests.get(f"{f_url}/read_all").json()
            if leader_data == f_data:
                print(f"Follower {i+1}: MATCH ({len(f_data)} keys)")
            else:
                print(
                    f"Follower {i+1}: MISMATCH (has {len(f_data)} keys, expected {len(leader_data)})")
                # Show some details about the mismatch
                missing_keys = set(leader_data.keys()) - set(f_data.keys())
                extra_keys = set(f_data.keys()) - set(leader_data.keys())
                if missing_keys:
                    print(f"  Missing keys: {list(missing_keys)[:5]}...")
                if extra_keys:
                    print(f"  Extra keys: {list(extra_keys)[:5]}...")
                all_match = False
        except Exception as e:
            print(f"Follower {i+1}: UNREACHABLE ({e})")
            all_match = False

    if all_match:
        print("SUCCESS: All replicas are consistent with Leader.")
    else:
        print("FAILURE: Inconsistencies found.")


def main():
    # Wait for docker to spin up
    print("Waiting for services to be ready...")
    time.sleep(5)

    quorums = [1, 2, 3, 4, 5]
    results = []

    for q in quorums:
        lat = run_benchmark(q)
        results.append(lat)

        # Wait for any background replication tasks to complete
        # This ensures pending operations from the current benchmark finish
        # before starting the next one
        print("Waiting for background replication to complete...")
        time.sleep(3)

        # Clear all stores to isolate each benchmark run
        clear_all_stores()
        print()

    # Run a final set of writes for consistency checking
    print("\n=== Running final writes for consistency check ===")
    final_quorum = 5  # Use highest quorum for consistency test
    set_quorum(final_quorum)

    # Write a fresh set of test data
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(50):
            k = f"test_key_{i}"
            v = f"test_val_{i}"
            futures.append(executor.submit(write_operation, k, v))

        for f in futures:
            f.result()  # Wait for all to complete

    print("\nWaiting for all final replications to complete...")
    time.sleep(5)

    check_consistency()

    plt.figure(figsize=(10, 6))
    plt.plot(quorums, results, marker='o')
    plt.title('Write Quorum vs Average Write Latency')
    plt.xlabel('Write Quorum (N confirmations)')
    plt.ylabel('Average Latency (ms)')
    plt.grid(True)
    plt.savefig('performance_plot.png')
    print("\nPlot saved to performance_plot.png")


if __name__ == "__main__":
    main()
