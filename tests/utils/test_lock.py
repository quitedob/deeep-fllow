# tests/utils/test_lock.py
import unittest
from unittest.mock import patch, MagicMock, call
import time
import uuid

# Assuming src is in PYTHONPATH or tests are run in a way that src can be imported
# Need to import redis for spec and RedisError
import redis
from src.utils import lock
from src.config import settings # To allow mocking settings if needed, though lock.py imports directly

# Save original Redis client from lock module if it's module-level, to restore it later
original_redis_client_in_lock = lock._redis_client

class TestRedisLock(unittest.TestCase):

    def setUp(self):
        # Create a new mock for each test to avoid interference
        self.mock_redis_client = MagicMock(spec=redis.Redis)

        # Patch the get_redis_client in the lock module to return our mock
        self.redis_patcher = patch('src.utils.lock.get_redis_client', return_value=self.mock_redis_client)
        self.mock_get_redis_client = self.redis_patcher.start()

        # Reset a global _redis_client in lock.py if it was directly initialized,
        # to ensure get_redis_client() is always called by the functions under test.
        lock._redis_client = None


    def tearDown(self):
        self.redis_patcher.stop()
        lock._redis_client = original_redis_client_in_lock # Restore original client

    def test_acquire_lock_success(self):
        session_id = "test_session_1"
        self.mock_redis_client.set.return_value = True # Simulate successful SET NX EX

        lock_id = lock.acquire_lock(session_id, timeout=10, wait=1)

        self.assertIsNotNone(lock_id)
        self.mock_redis_client.set.assert_called_once()
        args, kwargs = self.mock_redis_client.set.call_args
        self.assertEqual(args[0], f"lock:session:{session_id}") # key
        self.assertTrue(isinstance(args[1], str)) # lock_id (uuid)
        self.assertEqual(kwargs.get('nx'), True)
        self.assertEqual(kwargs.get('ex'), 10)

    @patch('src.utils.lock.time.sleep') # Patch time.sleep used by lock.py
    def test_acquire_lock_fail_wait_timeout(self, mock_sleep): # Renamed and refined
        session_id = "test_session_2_fail_timeout"
        self.mock_redis_client.set.return_value = None # Lock always held by someone else

        wait_duration = 0.1 # Wait for 0.1s (e.g. 2 sleep intervals of 0.05s)
        start_time = time.time()
        lock_id = lock.acquire_lock(session_id, timeout=10, wait=wait_duration)
        end_time = time.time()

        self.assertIsNone(lock_id)
        self.assertGreaterEqual(end_time - start_time, wait_duration)

        # Check that set was called multiple times due to retry loop.
        # For wait_duration = 0.1s and sleep_interval = 0.05s:
        # Iteration 1: set() fails. sleep(0.05). (set_calls=1, sleep_calls=1 if loop continues)
        # Iteration 2: set() fails. sleep(0.05). (set_calls=2, sleep_calls=2 if loop continues)
        # Loop terminates because time limit exceeded.
        # Number of set attempts should be at least wait_duration / sleep_interval
        # It's tricky to be exact due to time.time() precision and small overheads.
        # Let's check set was called at least twice.
        self.assertGreaterEqual(self.mock_redis_client.set.call_count, 2)

        # If set was called N times and all failed, sleep should be called N times
        # because sleep is called after every failed set attempt within the loop.
        if self.mock_redis_client.set.call_count > 0: # Ensure set was called at least once
            self.assertEqual(mock_sleep.call_count, self.mock_redis_client.set.call_count)
            mock_sleep.assert_any_call(0.05) # Check sleep duration

    @patch('src.utils.lock.time.sleep') # Patch time.sleep
    def test_acquire_lock_success_on_retry(self, mock_sleep):
        session_id = "test_session_3"
        # Fail first, then succeed
        self.mock_redis_client.set.side_effect = [None, True]

        lock_id = lock.acquire_lock(session_id, timeout=10, wait=1)

        self.assertIsNotNone(lock_id)
        self.assertEqual(self.mock_redis_client.set.call_count, 2)
        mock_sleep.assert_called_once_with(0.05) # Ensure it slept with 0.05

    def test_release_lock_success(self):
        session_id = "test_session_4"
        lock_id_val = str(uuid.uuid4())

        self.mock_redis_client.eval.return_value = 1

        released = lock.release_lock(session_id, lock_id_val)

        self.assertTrue(released)
        self.mock_redis_client.eval.assert_called_once()

        args, _ = self.mock_redis_client.eval.call_args
        expected_lua_script = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
        # Compare scripts, removing leading/trailing whitespace from each line
        self.assertEqual(
            [line.strip() for line in args[0].strip().split('\n')],
            [line.strip() for line in expected_lua_script.strip().split('\n')]
        )
        self.assertEqual(args[1], 1) # numkeys
        self.assertEqual(args[2], f"lock:session:{session_id}") # KEYS[1]
        self.assertEqual(args[3], lock_id_val) # ARGV[1]


    def test_release_lock_fail_wrong_lock_id(self):
        session_id = "test_session_5"
        lock_id_val = str(uuid.uuid4())

        self.mock_redis_client.eval.return_value = 0

        released = lock.release_lock(session_id, lock_id_val)

        self.assertFalse(released)
        self.mock_redis_client.eval.assert_called_once()

    def test_release_lock_redis_error(self):
        session_id = "test_session_6"
        lock_id_val = str(uuid.uuid4())

        # Simulate the specific error caught in lock.py
        self.mock_redis_client.eval.side_effect = redis.RedisError("Simulated Redis Error")

        released = lock.release_lock(session_id, lock_id_val)

        self.assertFalse(released) # Ensure it returns False on RedisError
        self.mock_redis_client.eval.assert_called_once()

    def test_acquire_lock_passes_timeout_correctly(self):
        session_id = "test_session_timeout"
        self.mock_redis_client.set.return_value = True

        custom_timeout = 30
        lock.acquire_lock(session_id, timeout=custom_timeout, wait=1)

        self.mock_redis_client.set.assert_called_once()
        _, kwargs = self.mock_redis_client.set.call_args
        self.assertEqual(kwargs.get('ex'), custom_timeout)

if __name__ == '__main__':
    unittest.main()
