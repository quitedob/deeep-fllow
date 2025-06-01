# tests/workers/test_session_worker.py
# -*- coding: utf-8 -*-
import pytest
import fakeredis
import threading
import time
import json
from unittest.mock import MagicMock

import src.workers.session_worker as worker_mod
import src.utils.cache as cache_mod # Import for monkeypatching

@pytest.fixture(autouse=True)
def fake_redis_and_run(monkeypatch):
    fake_r = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(worker_mod, "_redis", fake_r)

    mocked_run_langgraph = MagicMock()

    def fake_run_langgraph_impl(payload, session_id=None, use_sharded=True):
        current_topic = payload.get("topic")

        # Simulate run_langgraph saving state via cache_mod functions
        # which are now also using fake_r due to the patch below.
        if current_topic == "error_topic" or current_topic == "error_topic_loop": # Adjusted for loop test
            error_state_to_save = {"_session_id": session_id, "topic": current_topic, "error": "模拟错误"}
            cache_mod.set_state_sharded(session_id, error_state_to_save)
            return {"_session_id": session_id, "error": "模拟错误"}

        success_state_to_save = {
            "_session_id": session_id,
            "topic": current_topic,
            "tasks": ["t"],
            "research_results": {},
            "code_results": {},
            "report_paths": {"pdf": f"/tmp/{session_id}.pdf"}
        }
        cache_mod.set_state_sharded(session_id, success_state_to_save)
        return success_state_to_save

    mocked_run_langgraph.side_effect = fake_run_langgraph_impl
    monkeypatch.setattr(worker_mod, "run_langgraph", mocked_run_langgraph)

    # Monkeypatch src.utils.cache to use the same fakeredis instance
    # The cache module uses a module-level _redis_client that is initialized to None,
    # and get_redis_client() initializes it. So, we patch _redis_client.
    monkeypatch.setattr(cache_mod, "_redis_client", fake_r)
    # And ensure get_redis_client() if called directly by has_completed will use this.
    # Forcing re-init by setting original to None then calling get_redis_client() once,
    # or directly patching get_redis_client() in cache_mod.
    # The simplest is to ensure _redis_client in cache_mod points to fake_r,
    # as get_redis_client checks `if _redis_client is None`.
    # The setattr above should cover this.

    yield fake_r, mocked_run_langgraph # Yield both for potential assertions

def push_task(fake_redis_client, session_id, topic):
    task = {"session_id": session_id, "topic": topic}
    fake_redis_client.lpush("queue:session_tasks", json.dumps(task))

def test_worker_success_and_skip(fake_redis_and_run):
    fake_r_client, mock_run_langgraph = fake_redis_and_run

    # 1. Push a normal task
    push_task(fake_r_client, "sessA", "normal_topic")

    task = worker_mod.consume_queue(block=False)
    assert task is not None, "Task should be consumed from queue"
    assert task == {"session_id": "sessA", "topic": "normal_topic"}

    # Before run_langgraph is called by the test/worker, state should not exist
    assert worker_mod.has_completed("sessA") is False, "State should not exist before run_langgraph for sessA"

    # Simulate run_langgraph call (as worker_loop would do)
    # Our mocked run_langgraph (fake_run_langgraph_impl) will save state.
    result = worker_mod.run_langgraph(payload={"topic": "normal_topic"}, session_id="sessA", use_sharded=True)
    assert "report_paths" in result, "Mocked run_langgraph should return report_paths"

    # After run_langgraph, has_completed should be True
    assert worker_mod.has_completed("sessA") is True, "has_completed should be True after mocked run_langgraph"

    # 2. Push same session again; worker_loop would skip it.
    push_task(fake_r_client, "sessA", "normal_topic_again")

    task2 = worker_mod.consume_queue(block=False)
    assert task2 is not None
    assert task2['session_id'] == 'sessA'

    # If worker_loop were to process this, it would call has_completed first.
    assert worker_mod.has_completed("sessA") is True, "has_completed should still be True for sessA, leading to a skip"

def test_worker_error_handling(fake_redis_and_run):
    fake_r_client, mock_run_langgraph = fake_redis_and_run

    push_task(fake_r_client, "sessErr", "error_topic")

    task = worker_mod.consume_queue(block=False)
    assert task == {"session_id": "sessErr", "topic": "error_topic"}

    # Simulate worker calling run_langgraph
    result = worker_mod.run_langgraph(payload={"topic": "error_topic"}, session_id="sessErr", use_sharded=True)
    assert "error" in result and "模拟错误" in result["error"]

    # has_completed should also return True because an error state was saved by the mock
    assert worker_mod.has_completed("sessErr") is True

def test_worker_loop_integration(fake_redis_and_run):
    fake_r_client, mocked_run_langgraph_from_fixture = fake_redis_and_run

    push_task(fake_r_client, "sessLoop1", "normal_topic_loop")
    push_task(fake_r_client, "sessLoop2", "error_topic_loop")

    processed_items_count = 0

    # Get the original side_effect from the fixture's mock
    original_side_effect = mocked_run_langgraph_from_fixture.side_effect

    def run_langgraph_counter_side_effect(*args, **kwargs):
        nonlocal processed_items_count
        processed_items_count +=1
        return original_side_effect(*args, **kwargs) # Call the fixture's fake_run_langgraph_impl

    # Temporarily wrap the side_effect to count calls
    mocked_run_langgraph_from_fixture.side_effect = run_langgraph_counter_side_effect

    worker_thread = threading.Thread(target=worker_mod.session_worker_loop, daemon=True)
    worker_thread.start()

    max_wait_time = 2
    start_wait = time.time()
    while processed_items_count < 2 and (time.time() - start_wait) < max_wait_time:
        time.sleep(0.05)

    # Restore original side_effect to avoid issues if mock is used elsewhere later
    mocked_run_langgraph_from_fixture.side_effect = original_side_effect

    assert processed_items_count == 2, f"Worker loop should have processed both tasks, processed: {processed_items_count}"

    assert worker_mod.has_completed("sessLoop1") is True
    assert worker_mod.has_completed("sessLoop2") is True # error_topic_loop also results in 'completed' state

    # Attempt to clean up the thread
    # To properly stop the loop for testing, session_worker_loop would need a global stop flag
    # or consume_queue could be mocked to raise an exception after N calls.
    # For now, rely on daemon thread for test exit.
    # We can try to interrupt its blocking call by closing the fake_r_client connection,
    # which might cause brpop to raise an error if fakeredis simulates that.
    # Or, more simply, just join with a very short timeout.
    worker_thread.join(timeout=0.1)
    # If using a global stop flag:
    # monkeypatch.setattr(worker_mod, "WORKER_SHOULD_RUN", False, raising=False) # Example
    # worker_thread.join()
