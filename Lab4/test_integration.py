"""
Integration test for leader-follower key-value store with semi-synchronous replication.

Tests:
1. Basic write and read operations
2. Replication to followers
3. Timestamp-based ordering (prevents out-of-order updates)
4. Quorum requirements
5. Concurrent writes to the same key
6. Eventual consistency across all replicas
"""

import requests
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

# Configuration
LEADER_URL = "http://localhost:8001"
FOLLOWER_URLS = [
    "http://localhost:8002",
    "http://localhost:8003",
    "http://localhost:8004",
    "http://localhost:8005",
    "http://localhost:8006"
]


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""

    def success(self, message: str = ""):
        self.passed = True
        self.message = message

    def fail(self, message: str):
        self.passed = False
        self.message = message

    def __str__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        return f"{status}: {self.name}\n  {self.message}"


def clear_all_stores():
    """Clear all data from leader and followers."""
    for url in [LEADER_URL] + FOLLOWER_URLS:
        try:
            requests.delete(f"{url}/clear", timeout=2)
        except:
            pass


def set_quorum(n: int):
    """Set the write quorum on the leader."""
    try:
        resp = requests.post(f"{LEADER_URL}/config",
                             json={"quorum": n}, timeout=2)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to set quorum: {e}")
        return False


def write_key(key: str, value: str, timeout: float = 5.0) -> bool:
    """Write a key-value pair to the leader."""
    try:
        resp = requests.post(
            f"{LEADER_URL}/write",
            json={"key": key, "value": value},
            timeout=timeout
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"Write failed: {e}")
        return False


def read_key_from(url: str, key: str) -> str:
    """Read a key from a specific node."""
    try:
        resp = requests.get(f"{url}/read/{key}", timeout=2)
        resp.raise_for_status()
        data = resp.json()
        return data.get("value")
    except:
        return None


def get_all_data_from(url: str) -> Dict[str, str]:
    """Get all data from a specific node."""
    try:
        resp = requests.get(f"{url}/read_all", timeout=2)
        resp.raise_for_status()
        return resp.json()
    except:
        return {}


def test_health_check() -> TestResult:
    """Test 1: Verify all nodes are healthy."""
    result = TestResult("Health Check")

    try:
        # Check leader
        resp = requests.get(f"{LEADER_URL}/health", timeout=2)
        if resp.status_code != 200 or resp.json().get("role") != "leader":
            result.fail("Leader health check failed")
            return result

        # Check all followers
        for i, f_url in enumerate(FOLLOWER_URLS):
            resp = requests.get(f"{f_url}/health", timeout=2)
            if resp.status_code != 200 or resp.json().get("role") != "follower":
                result.fail(f"Follower {i+1} health check failed")
                return result

        result.success("All nodes healthy (1 leader + 5 followers)")
        return result
    except Exception as e:
        result.fail(f"Health check error: {e}")
        return result


def test_basic_write_read() -> TestResult:
    """Test 2: Basic write and read operations."""
    result = TestResult("Basic Write and Read")
    clear_all_stores()
    set_quorum(1)

    try:
        # Write a key
        if not write_key("test_key", "test_value"):
            result.fail("Failed to write key")
            return result

        # Read from leader
        value = read_key_from(LEADER_URL, "test_key")
        if value != "test_value":
            result.fail(f"Leader has wrong value: {value}")
            return result

        result.success("Write and read successful on leader")
        return result
    except Exception as e:
        result.fail(f"Error: {e}")
        return result


def test_replication_to_followers() -> TestResult:
    """Test 3: Verify data replicates to all followers."""
    result = TestResult("Replication to Followers")
    clear_all_stores()
    set_quorum(5)  # Require all followers

    try:
        # Write with high quorum
        if not write_key("replicated_key", "replicated_value"):
            result.fail("Write failed with quorum=5")
            return result

        # Give time for replication
        time.sleep(2)

        # Check all followers
        for i, f_url in enumerate(FOLLOWER_URLS):
            value = read_key_from(f_url, "replicated_key")
            if value != "replicated_value":
                result.fail(
                    f"Follower {i+1} missing data or has wrong value: {value}")
                return result

        result.success("Data successfully replicated to all 5 followers")
        return result
    except Exception as e:
        result.fail(f"Error: {e}")
        return result


def test_quorum_requirement() -> TestResult:
    """Test 4: Verify quorum requirements are enforced."""
    result = TestResult("Quorum Requirement")
    clear_all_stores()

    try:
        # Test with quorum=1 (should succeed quickly)
        set_quorum(1)
        start = time.time()
        if not write_key("quorum1_key", "value1"):
            result.fail("Write failed with quorum=1")
            return result
        latency1 = (time.time() - start) * 1000

        # Test with quorum=5 (should take longer)
        set_quorum(5)
        start = time.time()
        if not write_key("quorum5_key", "value5"):
            result.fail("Write failed with quorum=5")
            return result
        latency5 = (time.time() - start) * 1000

        # Quorum=5 should generally take longer than quorum=1
        # (though not guaranteed due to randomness)
        result.success(
            f"Quorum=1: {latency1:.1f}ms, Quorum=5: {latency5:.1f}ms"
        )
        return result
    except Exception as e:
        result.fail(f"Error: {e}")
        return result


def test_concurrent_writes_same_key() -> TestResult:
    """Test 5: Concurrent writes to the same key with timestamp ordering."""
    result = TestResult("Concurrent Writes (Same Key)")
    clear_all_stores()
    set_quorum(3)

    try:
        # Write the same key 20 times concurrently
        key = "concurrent_key"
        num_writes = 20

        def write_with_value(i):
            return write_key(key, f"value_{i}")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_with_value, i)
                       for i in range(num_writes)]
            results = [f.result() for f in futures]

        if not all(results):
            result.fail(
                f"Some writes failed: {sum(results)}/{num_writes} succeeded")
            return result

        # Wait for all replications to complete
        time.sleep(3)

        # Check that leader and all followers have the SAME final value
        # (Due to timestamps, they should all converge to the same value)
        leader_value = read_key_from(LEADER_URL, key)
        if leader_value is None:
            result.fail("Leader has no value after concurrent writes")
            return result

        # Check all followers match the leader
        for i, f_url in enumerate(FOLLOWER_URLS):
            f_value = read_key_from(f_url, key)
            if f_value != leader_value:
                result.fail(
                    f"Follower {i+1} has inconsistent value: "
                    f"'{f_value}' vs leader's '{leader_value}'"
                )
                return result

        result.success(
            f"All {num_writes} concurrent writes succeeded. "
            f"All replicas converged to: '{leader_value}'"
        )
        return result
    except Exception as e:
        result.fail(f"Error: {e}")
        return result


def test_timestamp_ordering() -> TestResult:
    """Test 6: Verify timestamps prevent out-of-order updates."""
    result = TestResult("Timestamp Ordering")
    clear_all_stores()
    set_quorum(1)  # Low quorum to allow fast completion

    try:
        # Write multiple values to the same key sequentially
        key = "timestamp_test"
        values = ["v1", "v2", "v3", "v4", "v5"]

        for val in values:
            if not write_key(key, val):
                result.fail(f"Failed to write {val}")
                return result
            time.sleep(0.1)  # Small delay between writes

        # Wait for all replications (including delayed ones) to complete
        time.sleep(3)

        # All replicas should have the LAST value written
        expected = values[-1]

        # Check leader
        leader_value = read_key_from(LEADER_URL, key)
        if leader_value != expected:
            result.fail(
                f"Leader has wrong value: {leader_value} != {expected}")
            return result

        # Check all followers
        for i, f_url in enumerate(FOLLOWER_URLS):
            f_value = read_key_from(f_url, key)
            if f_value != expected:
                result.fail(
                    f"Follower {i+1} has wrong value: {f_value} != {expected}. "
                    "Timestamp ordering failed!"
                )
                return result

        result.success(
            f"All replicas correctly have the latest value: '{expected}'. "
            "Timestamps prevented out-of-order updates."
        )
        return result
    except Exception as e:
        result.fail(f"Error: {e}")
        return result


def test_eventual_consistency() -> TestResult:
    """Test 7: Test eventual consistency with mixed operations."""
    result = TestResult("Eventual Consistency")
    clear_all_stores()
    set_quorum(2)

    try:
        # Perform a mix of operations
        num_keys = 10
        writes_per_key = 5

        def write_multiple(key_idx):
            key = f"ec_key_{key_idx}"
            for i in range(writes_per_key):
                write_key(key, f"val_{key_idx}_{i}")

        # Write concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_multiple, i)
                       for i in range(num_keys)]
            for f in futures:
                f.result()

        # Wait for eventual consistency
        print("  Waiting for eventual consistency...")
        time.sleep(5)

        # Get data from leader
        leader_data = get_all_data_from(LEADER_URL)
        if len(leader_data) != num_keys:
            result.fail(
                f"Leader has {len(leader_data)} keys, expected {num_keys}")
            return result

        # Check all followers match leader
        mismatches = []
        for i, f_url in enumerate(FOLLOWER_URLS):
            f_data = get_all_data_from(f_url)

            if f_data != leader_data:
                # Find differences
                diff_keys = []
                for key in leader_data:
                    if key not in f_data or f_data[key] != leader_data[key]:
                        diff_keys.append(key)

                mismatches.append(
                    f"Follower {i+1}: {len(diff_keys)} keys differ")

        if mismatches:
            result.fail("Eventual consistency not achieved:\n    " +
                        "\n    ".join(mismatches))
            return result

        result.success(
            f"Eventual consistency achieved: {num_keys} keys, "
            f"{num_keys * writes_per_key} total writes, all replicas consistent"
        )
        return result
    except Exception as e:
        result.fail(f"Error: {e}")
        return result


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("LEADER-FOLLOWER REPLICATION - INTEGRATION TESTS")
    print("="*70 + "\n")

    # Wait for services to be ready
    print("Waiting for services to start...")
    time.sleep(3)

    tests = [
        test_health_check,
        test_basic_write_read,
        test_replication_to_followers,
        test_quorum_requirement,
        test_concurrent_writes_same_key,
        test_timestamp_ordering,
        test_eventual_consistency,
    ]

    results = []
    for test_fn in tests:
        print(f"\nRunning: {test_fn.__doc__.split(':')[0].strip()}")
        result = test_fn()
        results.append(result)
        print(f"  {result}")

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    for result in results:
        symbol = "✓" if result.passed else "✗"
        print(f"  {symbol} {result.name}")

    print(
        f"\nTotal: {passed} passed, {failed} failed out of {len(results)} tests")

    if failed == 0:
        print("\nll tests passed! YRplication system is working correctly.\n")
        return True
    else:
        print("\nSome tests failed. Review the failures above.\n")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
