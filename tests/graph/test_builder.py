# tests/graph/test_builder.py
import unittest
from unittest.mock import patch, MagicMock, ANY, call
import uuid
import json # For pubsub message parsing
import time # For pubsub message parsing
import threading # For concurrency test

from src.graph import builder # Ensure this imports the updated builder
from src.graph.builder import StateSchema # For type hints if needed
import redis # For spec and errors

class TestRunLanggraph(unittest.TestCase): # Renamed class for clarity

    def setUp(self):
        # Mock all external dependencies of run_langgraph
        self.patchers = []

        mock_specs = {
            'get_state_sharded': None, 'set_state_sharded': None,
            'delete_state_sharded': None, 'get_state': None,
            'set_state': None, 'delete_state': None,
            'acquire_lock': "test_lock_id", # Default successful lock
            'release_lock': True,
            # build_graph_with_memory returns a mock graph object
            'build_graph_with_memory': MagicMock(name="mock_graph_instance_creator"),
        }

        for func_name, return_val_or_mock_creator in mock_specs.items():
            patcher = patch(f'src.graph.builder.{func_name}')
            mock_func = patcher.start()

            if func_name == 'build_graph_with_memory':
                self.mock_graph_instance = MagicMock(name="mock_graph_instance") # self.mock_graph_instance is now defined
                mock_func.return_value = self.mock_graph_instance
            # Check if it's a spec for a mock (like MagicMock itself being passed in mock_specs)
            # or a direct return value. This logic ensures None is correctly set.
            elif isinstance(return_val_or_mock_creator, MagicMock):
                mock_func.return_value = return_val_or_mock_creator
            else: # Covers direct values including None, strings, booleans
                mock_func.return_value = return_val_or_mock_creator

            self.patchers.append(patcher)
            setattr(self, f'mock_{func_name}', mock_func)

        self.mock_pubsub_client = MagicMock(spec=redis.Redis)
        pubsub_patcher = patch('src.graph.builder._pubsub', self.mock_pubsub_client)
        self.mock_pubsub_client_instance = pubsub_patcher.start()
        self.patchers.append(pubsub_patcher)

        # Configure the mock graph and runnable
        # self.mock_graph_instance is already created if build_graph_with_memory was in mock_specs
        # and it's assigned to self.mock_build_graph_with_memory.return_value
        self.mock_runnable_instance = MagicMock(name="mock_runnable_instance")
        if hasattr(self, 'mock_graph_instance'): # Should exist due to build_graph_with_memory mock
             self.mock_graph_instance.compile.return_value = self.mock_runnable_instance
        else:
            # Fallback or error if build_graph_with_memory wasn't mocked as expected
            # This case should ideally not be hit if mock_specs is correct.
            pass

        self.mock_runnable_instance.invoke.side_effect = lambda state_dict: {**state_dict, "processed_by_graph": True}


    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()

    def test_new_session_sharded_success(self):
        initial_state = {"topic": "sharded_success"}
        generated_session_id = "new_session_uuid"

        mock_uuid_obj = MagicMock()
        mock_uuid_obj.__str__.return_value = generated_session_id
        with patch('src.graph.builder.uuid.uuid4', return_value=mock_uuid_obj):
            result = builder.run_langgraph(initial_state, session_id=None, use_sharded=True)

        self.mock_get_state_sharded.assert_not_called() # Not called if session_id is initially None
        self.mock_acquire_lock.assert_called_once_with(generated_session_id, timeout=30, wait=10)

        expected_state_for_invoke = {"topic": "sharded_success", "_session_id": generated_session_id}
        self.mock_runnable_instance.invoke.assert_called_once_with(expected_state_for_invoke)

        expected_final_state = {**expected_state_for_invoke, "processed_by_graph": True}
        self.mock_set_state_sharded.assert_called_once_with(generated_session_id, expected_final_state)
        self.mock_release_lock.assert_called_once_with(generated_session_id, "test_lock_id")

        self.assertEqual(result, expected_final_state)

        pubsub_calls = self.mock_pubsub_client.publish.call_args_list
        self.assertEqual(len(pubsub_calls), 2)
        start_event = json.loads(pubsub_calls[0][0][1])
        complete_event = json.loads(pubsub_calls[1][0][1])
        self.assertEqual(start_event["status"], "START")
        self.assertEqual(start_event["node"], "ALL")
        self.assertEqual(start_event["session_id"], generated_session_id)
        self.assertEqual(complete_event["status"], "COMPLETE")
        self.assertEqual(complete_event["node"], "ALL")
        self.assertEqual(complete_event["session_id"], generated_session_id)

    def test_existing_session_non_sharded_success(self):
        session_id = "existing_session_1"
        # _session_id from loaded state should be overridden by the session_id parameter if different,
        # but here they are the same. run_langgraph ensures current_state["_session_id"] = session_id param.
        loaded_state = {"topic": "loaded_topic", "value": 1}
        self.mock_get_state.return_value = loaded_state
        initial_input_state = {"new_value": 2}

        result = builder.run_langgraph(initial_input_state, session_id=session_id, use_sharded=False)

        self.mock_get_state.assert_called_once_with(session_id)
        self.mock_acquire_lock.assert_called_once_with(session_id, timeout=30, wait=10)

        # current_state.update(initial_state) then current_state["_session_id"] = session_id
        expected_state_for_invoke = {"topic": "loaded_topic", "value": 1, "new_value": 2, "_session_id": session_id}
        self.mock_runnable_instance.invoke.assert_called_once_with(expected_state_for_invoke)

        expected_final_state = {**expected_state_for_invoke, "processed_by_graph": True}
        self.mock_set_state.assert_called_once_with(session_id, expected_final_state)
        self.mock_release_lock.assert_called_once_with(session_id, "test_lock_id")
        self.assertEqual(result, expected_final_state)


    def test_lock_acquisition_fails(self):
        session_id = "lock_fail_session"
        self.mock_acquire_lock.return_value = None
        initial_state = {"topic": "any_topic"}

        result = builder.run_langgraph(initial_state, session_id=session_id)

        self.mock_acquire_lock.assert_called_once_with(session_id, timeout=30, wait=10)
        self.assertEqual(result, {"_session_id": session_id, "error": "会话正在执行，请稍后重试"})
        self.mock_runnable_instance.invoke.assert_not_called()
        self.mock_release_lock.assert_not_called()
        self.mock_pubsub_client.publish.assert_not_called()


    def test_topic_missing_error(self):
        session_id = "no_topic_session"
        self.mock_get_state_sharded.return_value = None # New session, empty state

        result = builder.run_langgraph({}, session_id=session_id, use_sharded=True) # Empty initial_state

        self.mock_acquire_lock.assert_called_once_with(session_id, timeout=30, wait=10)

        pubsub_calls = self.mock_pubsub_client.publish.call_args_list
        # When topic is missing, "ALL START" is not published. Only "ALL ERROR".
        self.assertEqual(len(pubsub_calls), 1, f"Expected 1 pubsub call for ERROR, got {len(pubsub_calls)}: {pubsub_calls}")
        error_event = json.loads(pubsub_calls[0][0][1]) # First (and only) call should be ERROR

        # self.assertEqual(start_event["status"], "START") # No START event
        self.assertEqual(error_event["status"], "ERROR")
        self.assertEqual(error_event["error"], "缺少 'topic'，无法继续执行") # Error key is 'error' in pubsub

        # current_state before error: initial_state ({}) merged with loaded (None->{}), then _session_id added
        # So current_state = {"_session_id": session_id} when topic check fails.
        # Then error is added to this current_state.
        expected_error_state = {"_session_id": session_id, "error": "缺少 'topic'，无法继续执行"}
        self.mock_set_state_sharded.assert_called_once_with(session_id, expected_error_state)
        self.mock_runnable_instance.invoke.assert_not_called()
        self.mock_release_lock.assert_called_once_with(session_id, "test_lock_id")
        self.assertEqual(result, {"_session_id": session_id, "error": "缺少 'topic'，无法继续执行"})

    def test_graph_invocation_error(self):
        session_id = "graph_error_session"
        initial_state = {"topic": "graph_fail_topic"}
        simulated_exception = ValueError("Graph processing failed!")
        self.mock_runnable_instance.invoke.side_effect = simulated_exception

        result = builder.run_langgraph(initial_state, session_id=session_id, use_sharded=False)

        self.mock_acquire_lock.assert_called_once_with(session_id, timeout=30, wait=10)

        state_at_invoke_time = {"topic": "graph_fail_topic", "_session_id": session_id}
        self.mock_runnable_instance.invoke.assert_called_once_with(state_at_invoke_time)

        expected_error_state = {**state_at_invoke_time, "error": str(simulated_exception)}
        self.mock_set_state.assert_called_once_with(session_id, expected_error_state)

        self.mock_release_lock.assert_called_once_with(session_id, "test_lock_id")
        self.assertEqual(result, {"_session_id": session_id, "error": str(simulated_exception)})

        pubsub_calls = self.mock_pubsub_client.publish.call_args_list
        self.assertEqual(len(pubsub_calls), 2)
        error_event = json.loads(pubsub_calls[1][0][1])
        self.assertEqual(error_event["status"], "ERROR")
        self.assertEqual(error_event["error"], str(simulated_exception)) # Error key is 'error'

    def test_run_langgraph_concurrency_lock(self):
        session_id = "concurrent_session"
        results_list = []

        # Thread 1 gets the lock, Thread 2 fails
        self.mock_acquire_lock.side_effect = ["real_lock_id_thread1", None]

        # Make invoke take a little time to ensure thread2 tries lock while thread1 holds it
        def invoke_side_effect_with_delay(state_dict):
            time.sleep(0.1) # Simulate work
            return {**state_dict, "processed_by_graph": True, "thread_ran": threading.current_thread().name}
        self.mock_runnable_instance.invoke.side_effect = invoke_side_effect_with_delay

        def target_function(initial_state_topic, thread_name):
            # Each thread needs its own current_state if initial_state differs,
            # but run_langgraph handles loading/init internally.
            # We need to ensure that the mock_acquire_lock.side_effect is consumed correctly.
            # This test assumes that the global mocks are fine for threading.
            current_thread = threading.current_thread()
            current_thread.name = thread_name # Set thread name for identification
            res = builder.run_langgraph({"topic": initial_state_topic}, session_id=session_id)
            results_list.append(res)

        thread1 = threading.Thread(target=target_function, args=("topic_thread1", "Thread-1"))
        thread2 = threading.Thread(target=target_function, args=("topic_thread2", "Thread-2"))

        thread1.start()
        time.sleep(0.02) # Slight delay to ensure thread1 likely calls acquire_lock first
        thread2.start()

        thread1.join(timeout=2)
        thread2.join(timeout=2)

        self.assertEqual(len(results_list), 2)

        success_results = [r for r in results_list if "processed_by_graph" in r]
        lock_fail_results = [r for r in results_list if r.get("error") == "会话正在执行，请稍后重试"]

        self.assertEqual(len(success_results), 1, f"Expected 1 success, got {success_results}")
        self.assertEqual(len(lock_fail_results), 1, f"Expected 1 lock failure, got {lock_fail_results}")

        # Ensure release_lock was called for the thread that acquired the lock
        self.mock_release_lock.assert_called_once_with(session_id, "real_lock_id_thread1")

        # Check which thread actually ran the graph
        self.assertEqual(success_results[0].get("thread_ran"), "Thread-1")


if __name__ == '__main__':
    unittest.main()
