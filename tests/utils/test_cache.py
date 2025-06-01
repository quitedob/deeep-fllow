# tests/utils/test_cache.py
import unittest
from unittest.mock import patch, MagicMock, call
import json

# Assuming src is in PYTHONPATH
from src.utils import cache
from src.config import settings # For context, not directly used unless mocking settings
import redis # For spec and errors

# Save original Redis client from cache module
original_redis_client_in_cache = cache._redis_client

class TestRedisCache(unittest.TestCase):

    def setUp(self):
        self.mock_redis_client = MagicMock(spec=redis.Redis)
        self.redis_patcher = patch('src.utils.cache.get_redis_client', return_value=self.mock_redis_client)
        self.mock_get_redis_client = self.redis_patcher.start()
        cache._redis_client = None # Ensure get_redis_client is called

    def tearDown(self):
        self.redis_patcher.stop()
        cache._redis_client = original_redis_client_in_cache

    # --- Single Key State Tests ---
    def test_set_state_single_key(self):
        session_id = "session_single_1"
        state_data = {"topic": "test topic", "value": 123}
        cache.set_state(session_id, state_data, ex=3600)
        self.mock_redis_client.set.assert_called_once_with(
            f"state:{session_id}", json.dumps(state_data), ex=3600
        )

    def test_get_state_single_key_exists_and_refreshes_ttl(self): # Renamed
        session_id = "session_single_2"
        state_data = {"topic": "test topic"}
        self.mock_redis_client.get.return_value = json.dumps(state_data)

        retrieved_state = cache.get_state(session_id)

        self.assertEqual(retrieved_state, state_data)
        self.mock_redis_client.get.assert_called_once_with(f"state:{session_id}")
        self.mock_redis_client.expire.assert_called_once_with(f"state:{session_id}", 86400) # Verify TTL refresh

    def test_get_state_single_key_not_exists(self):
        session_id = "session_single_3"
        self.mock_redis_client.get.return_value = None

        retrieved_state = cache.get_state(session_id)

        self.assertIsNone(retrieved_state)
        self.mock_redis_client.get.assert_called_once_with(f"state:{session_id}")
        self.mock_redis_client.expire.assert_not_called()

    def test_delete_state_single_key(self):
        session_id = "session_single_4"
        cache.delete_state(session_id)
        self.mock_redis_client.delete.assert_called_once_with(f"state:{session_id}")

    # --- Sharded State Tests ---
    def test_set_state_sharded(self):
        session_id = "session_sharded_1"
        state_data = {
            "topic": "sharded topic", "tasks": ["task1"],
            "research_results": {"data": "research"},
            "code_results": {"code": "sample"},
            "report_paths": {"txt": "/path.txt"},
            "audio_path": "/audio.mp3"
        }
        expected_base = {
            "topic": "sharded topic", "tasks": ["task1"],
            "report_paths": {"txt": "/path.txt"},
            "audio_path": "/audio.mp3",
            "_session_id": None, # state_data doesn't have _session_id, so it's None
            "error": None        # state_data doesn't have error, so it's None
        }
        expected_research = {"data": "research"}
        expected_code = {"code": "sample"}

        cache.set_state_sharded(session_id, state_data, ex=7200)

        expected_calls_set = [
            call(f"state:{session_id}:base", json.dumps(expected_base), ex=7200),
            call(f"state:{session_id}:research", json.dumps(expected_research), ex=7200),
            call(f"state:{session_id}:code", json.dumps(expected_code), ex=7200),
        ]
        # Order of setting shards is deterministic
        self.mock_redis_client.set.assert_has_calls(expected_calls_set, any_order=False)
        self.assertEqual(self.mock_redis_client.set.call_count, 3)

    def test_set_state_sharded_missing_fields_defaults_to_empty_dict(self): # Renamed
        session_id = "session_sharded_missing"
        state_data = {"topic": "minimal topic"}

        expected_base = {
            "topic": "minimal topic", "tasks": None,
            "report_paths": None, "audio_path": None,
            "_session_id": None, # state_data doesn't have _session_id, so it's None
            "error": None        # state_data doesn't have error, so it's None
        }
        expected_research = {}
        expected_code = {}

        cache.set_state_sharded(session_id, state_data, ex=3600)

        expected_calls_set = [
            call(f"state:{session_id}:base", json.dumps(expected_base), ex=3600),
            call(f"state:{session_id}:research", json.dumps(expected_research), ex=3600),
            call(f"state:{session_id}:code", json.dumps(expected_code), ex=3600),
        ]
        self.mock_redis_client.set.assert_has_calls(expected_calls_set, any_order=False)


    def test_get_state_sharded_exists_and_refreshes_ttl(self): # Renamed
        session_id = "session_sharded_2"
        base_data = {"topic": "sharded topic", "tasks": ["task1"], "report_paths": None, "audio_path": None}
        research_data = {"data": "research"}
        code_data = {"code": "sample"}

        def get_side_effect(key):
            if key == f"state:{session_id}:base": return json.dumps(base_data)
            if key == f"state:{session_id}:research": return json.dumps(research_data)
            if key == f"state:{session_id}:code": return json.dumps(code_data)
            return None
        self.mock_redis_client.get.side_effect = get_side_effect

        retrieved_state = cache.get_state_sharded(session_id)

        expected_state = {
            "topic": "sharded topic", "tasks": ["task1"],
            "research_results": research_data, "code_results": code_data,
            "report_paths": None, "audio_path": None,
            "_session_id": None, "error": None # Added expected None for these new fields
        }
        self.assertEqual(retrieved_state, expected_state)

        get_calls = [ # Order of GETs is deterministic
            call(f"state:{session_id}:base"),
            call(f"state:{session_id}:research"),
            call(f"state:{session_id}:code"),
        ]
        self.mock_redis_client.get.assert_has_calls(get_calls, any_order=False)

        expire_calls = [ # Expire calls can be in any order relative to each other
            call(f"state:{session_id}:base", 86400),
            call(f"state:{session_id}:research", 86400),
            call(f"state:{session_id}:code", 86400),
        ]
        self.mock_redis_client.expire.assert_has_calls(expire_calls, any_order=True)
        self.assertEqual(self.mock_redis_client.expire.call_count, 3) # All 3 shards existed and should be refreshed


    def test_get_state_sharded_base_not_exists(self):
        session_id = "session_sharded_3"
        self.mock_redis_client.get.side_effect = lambda key: None if key == f"state:{session_id}:base" else json.dumps({"other":"data"})

        retrieved_state = cache.get_state_sharded(session_id)
        self.assertIsNone(retrieved_state)
        self.mock_redis_client.get.assert_called_once_with(f"state:{session_id}:base")
        self.mock_redis_client.expire.assert_not_called()

    def test_get_state_sharded_research_or_code_not_exist_refreshes_existing_ttl(self): # Renamed
        session_id = "session_sharded_partial"
        base_data = {"topic": "partial topic", "tasks": [], "report_paths": None, "audio_path": None}
        code_data = {"code": "some code"} # research_data will be missing

        def get_side_effect(key):
            if key == f"state:{session_id}:base": return json.dumps(base_data)
            if key == f"state:{session_id}:research": return None # Research missing
            if key == f"state:{session_id}:code": return json.dumps(code_data)
            return None
        self.mock_redis_client.get.side_effect = get_side_effect

        retrieved_state = cache.get_state_sharded(session_id)
        expected_state = {
            "topic": "partial topic", "tasks": [],
            "research_results": {}, # Defaults to empty dict because research_data was None
            "code_results": code_data,
            "report_paths": None, "audio_path": None,
            "_session_id": None, "error": None # Added expected None for these new fields
        }
        self.assertEqual(retrieved_state, expected_state)

        expected_expire_calls = [
            call(f"state:{session_id}:base", 86400),
            call(f"state:{session_id}:code", 86400), # research shard was missing, so not expired
        ]
        self.mock_redis_client.expire.assert_has_calls(expected_expire_calls, any_order=True)
        self.assertEqual(self.mock_redis_client.expire.call_count, 2) # Only base and code shards refreshed

        # Explicitly check research shard was NOT expired
        research_expire_called = any(
            c == call(f"state:{session_id}:research", 86400)
            for c in self.mock_redis_client.expire.call_args_list
        )
        self.assertFalse(research_expire_called, "Expire should not be called on a non-existent research shard")


    def test_delete_state_sharded(self):
        session_id = "session_sharded_4"
        cache.delete_state_sharded(session_id)
        self.mock_redis_client.delete.assert_called_once_with(
            f"state:{session_id}:base",
            f"state:{session_id}:research",
            f"state:{session_id}:code"
        )

    # --- Queue Tests ---
    def test_enqueue_session(self):
        session_id = "session_q_1"
        topic = "queue topic"
        expected_item = json.dumps({"session_id": session_id, "topic": topic})
        cache.enqueue_session(session_id, topic)
        self.mock_redis_client.lpush.assert_called_once_with(cache.QUEUE_NAME, expected_item)

    def test_dequeue_session_blocking_success(self):
        session_id = "session_q_2"
        topic = "queued topic"
        item_json = json.dumps({"session_id": session_id, "topic": topic})
        self.mock_redis_client.brpop.return_value = (cache.QUEUE_NAME.encode('utf-8'), item_json.encode('utf-8'))
        task = cache.dequeue_session(block=True, timeout=1)
        self.assertEqual(task, {"session_id": session_id, "topic": topic})
        self.mock_redis_client.brpop.assert_called_once_with(cache.QUEUE_NAME, timeout=1)

    def test_dequeue_session_blocking_timeout(self):
        self.mock_redis_client.brpop.return_value = None
        task = cache.dequeue_session(block=True, timeout=1)
        self.assertIsNone(task)

    def test_dequeue_session_non_blocking_success(self):
        session_id = "session_q_3"
        topic = "nonblock topic"
        item_json = json.dumps({"session_id": session_id, "topic": topic})
        self.mock_redis_client.rpop.return_value = item_json
        task = cache.dequeue_session(block=False)
        self.assertEqual(task, {"session_id": session_id, "topic": topic})

    def test_dequeue_session_non_blocking_empty(self):
        self.mock_redis_client.rpop.return_value = None
        task = cache.dequeue_session(block=False)
        self.assertIsNone(task)

    # --- Secondary Cache Tests ---
    def test_cache_result(self):
        cache_key = "my_cache_key_1"
        value = {"data": "important result"}
        cache.cache_result(cache_key, value, ex=1800)
        self.mock_redis_client.set.assert_called_once_with(
            cache_key, json.dumps(value), ex=1800
        )

    def test_get_cached_exists(self):
        cache_key = "my_cache_key_2"
        value = {"data": "cached data"}
        self.mock_redis_client.get.return_value = json.dumps(value)
        retrieved_value = cache.get_cached(cache_key)
        self.assertEqual(retrieved_value, value)

    def test_get_cached_not_exists(self):
        cache_key = "my_cache_key_3"
        self.mock_redis_client.get.return_value = None
        retrieved_value = cache.get_cached(cache_key)
        self.assertIsNone(retrieved_value)

if __name__ == '__main__':
    unittest.main()
