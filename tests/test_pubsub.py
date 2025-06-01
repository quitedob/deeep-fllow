# tests/test_pubsub.py
# -*- coding: utf-8 -*-
import pytest
import fakeredis
import json
import time

# 依次导入三个 Agent 模块
from src.agents import planner as planner_mod # Function is planner_agent
from src.agents import research_agent as research_mod # Function is research_agent
from src.agents import coder_agent as coder_mod # Function is coder_agent

# Ensure the cache utility is imported if agents use get_cached/cache_result,
# and monkeypatch its _redis_client too if those are called within agent logic.
import src.utils.cache as cache_mod

# Use the fixture name as defined in the user's latest snippet: fake_redis
@pytest.fixture(autouse=True)
def fake_redis(monkeypatch): # User's snippet uses 'fake_redis'
    fake = fakeredis.FakeRedis(decode_responses=True)
    # 将三个模块的 _pubsub 都指向同一个 FakeRedis
    monkeypatch.setattr(planner_mod,  "_pubsub", fake)
    monkeypatch.setattr(research_mod, "_pubsub", fake)
    monkeypatch.setattr(coder_mod,    "_pubsub", fake)

    # Patching _redis_client for cache_mod.
    # src.utils.cache.get_redis_client() uses the module-level _redis_client.
    # Setting this ensures that get_cached/cache_result in agents use FakeRedis.
    monkeypatch.setattr(cache_mod, "_redis_client", fake)
    return fake

def test_planner_pubsub_messages(fake_redis): # Use user's fixture name
    session_id = "sess-1" # Using unique session IDs for clarity
    channel = f"channel:session:{session_id}"
    pubsub = fake_redis.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)

    state = {"topic": "TestTopicPlanner", "_session_id": session_id}
    planner_mod.planner_agent(state) # Call the correct function name

    time.sleep(0.05) # Give time for messages to publish

    msgs = []
    start_listen_time = time.time()
    while time.time() - start_listen_time < 0.2: # Listen for 0.2 seconds
        raw = pubsub.get_message(timeout=0.01)
        if not raw:
            time.sleep(0.01) # Small pause if no message
            continue
        msgs.append(json.loads(raw["data"]))

    pubsub.unsubscribe(channel)
    pubsub.close()

    assert any(m["node"] == "planner"  and m["status"] == "START"    for m in msgs), f"Planner START not found in {msgs}"
    assert any(m["node"] == "planner"  and m["status"] == "COMPLETE" for m in msgs), f"Planner COMPLETE not found in {msgs}"

def test_researcher_pubsub_messages(fake_redis):
    session_id = "sess-2"
    channel = f"channel:session:{session_id}"
    pubsub = fake_redis.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)

    state = {"topic": "TestTopicResearcher", "_session_id": session_id}
    research_mod.research_agent(state) # Call the correct function name

    time.sleep(0.05)
    msgs = []
    start_listen_time = time.time()
    while time.time() - start_listen_time < 0.2: # Listen for 0.2 seconds
        raw = pubsub.get_message(timeout=0.01)
        if not raw:
            time.sleep(0.01) # Small pause if no message
            continue
        msgs.append(json.loads(raw["data"]))

    pubsub.unsubscribe(channel)
    pubsub.close()

    assert any(m["node"] == "researcher"  and m["status"] == "START"    for m in msgs), f"Researcher START not found in {msgs}"
    assert any(m["node"] == "researcher"  and m["status"] == "COMPLETE" for m in msgs), f"Researcher COMPLETE not found in {msgs}"

def test_coder_pubsub_messages(fake_redis):
    session_id = "sess-3"
    channel = f"channel:session:{session_id}"
    pubsub = fake_redis.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)

    state = {"topic": "TestTopicCoder", "_session_id": session_id}
    coder_mod.coder_agent(state) # Call the correct function name

    time.sleep(0.05)
    msgs = []
    start_listen_time = time.time()
    while time.time() - start_listen_time < 0.2: # Listen for 0.2 seconds
        raw = pubsub.get_message(timeout=0.01)
        if not raw:
            time.sleep(0.01) # Small pause if no message
            continue
        msgs.append(json.loads(raw["data"]))

    pubsub.unsubscribe(channel)
    pubsub.close()

    assert any(m["node"] == "coder"  and m["status"] == "START"    for m in msgs), f"Coder START not found in {msgs}"
    assert any(m["node"] == "coder"  and m["status"] == "COMPLETE" for m in msgs), f"Coder COMPLETE not found in {msgs}"

# To run these tests:
# Ensure pytest and fakeredis are installed:
# pip install pytest fakeredis
# From the project root directory (containing 'src' and 'tests'):
# pytest tests/test_pubsub.py
