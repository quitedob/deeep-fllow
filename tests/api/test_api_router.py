# tests/api/test_api_router.py
# -*- coding: utf-8 -*-
"""
API Router 单元测试：使用 TestClient 访问 /api/queue_length 与 /api/failure_rate，
并对 API Key 鉴权、正确返回值进行验证。
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends, HTTPException, Header
from typing import List
from unittest.mock import patch # Added for @patch.object

# Modules to be tested or whose functions are called by the router
from src.api import api_router
from src.config import settings
from src.workers import queue_monitor
from src.workers import alert

# API_KEYS for the test app
TEST_API_KEYS: List[str] = ["testkey1", "testkey2"]

async def verify_api_key_for_test(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=403, detail="API Key header missing")
    if x_api_key not in TEST_API_KEYS: # Uses TEST_API_KEYS defined in this test file
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return x_api_key

# Create a minimal FastAPI app for testing the router via a fixture
@pytest.fixture
def test_app_client():
    app = FastAPI()
    app.include_router(api_router.router, dependencies=[Depends(verify_api_key_for_test)])
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def mock_worker_functions_for_success(): # Renamed to be specific for success cases
    # Patch the names as they are resolved/imported within api_router.py
    patcher_get_queue_length = patch('src.api.api_router.get_queue_length', return_value=123)
    patcher_get_failure_rate = patch('src.api.api_router.get_failure_rate', return_value=0.07)

    # Start the patchers
    mock_get_queue_length = patcher_get_queue_length.start()
    mock_get_failure_rate = patcher_get_failure_rate.start()

    yield mock_get_queue_length, mock_get_failure_rate # Yield the mocks if tests need to assert on them

    # Stop the patchers
    patcher_get_queue_length.stop()
    patcher_get_failure_rate.stop()

    # Note: settings.API_KEYS is not directly patched here anymore because
    # verify_api_key_for_test now uses its own local TEST_API_KEYS list.
    # If verify_api_key (from server/app.py) were imported and used,
    # then patching settings.API_KEYS would be necessary.

def get_auth_headers():
    return {"x-api-key": TEST_API_KEYS[0]}

def test_get_queue_length_success(test_app_client, mock_worker_functions_for_success): # Use new fixtures
    response = test_app_client.get("/api/queue_length", headers=get_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert "queue_length" in data and data["queue_length"] == 123

def test_get_failure_rate_success(test_app_client, mock_worker_functions_for_success): # Use new fixtures
    response = test_app_client.get("/api/failure_rate", headers=get_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert "failure_rate" in data
    # For float comparison, pytest.approx is good practice
    assert data["failure_rate"] == pytest.approx(0.07)


def test_missing_api_key_for_queue_length(test_app_client): # Use new fixture
    response = test_app_client.get("/api/queue_length") # No headers
    assert response.status_code == 403
    assert "API Key header missing" in response.json().get("detail", "")


def test_invalid_api_key_for_failure_rate(test_app_client): # Use new fixture
    response = test_app_client.get("/api/failure_rate", headers={"x-api-key": "badkey"})
    assert response.status_code == 403
    assert "Invalid API Key" in response.json().get("detail", "")

@patch('src.api.api_router.get_queue_length', side_effect=Exception("Test_Queue_Error"))
def test_get_queue_length_handles_exception(mock_get_q_len_specific, test_app_client): # Use new fixture
    response = test_app_client.get("/api/queue_length", headers=get_auth_headers())
    assert response.status_code == 500
    assert "Test_Queue_Error" in response.json().get("detail", "")

@patch('src.api.api_router.get_failure_rate', side_effect=Exception("Test_Rate_Error"))
def test_get_failure_rate_handles_exception(mock_get_f_rate_specific, test_app_client): # Use new fixture
    response = test_app_client.get("/api/failure_rate", headers=get_auth_headers())
    assert response.status_code == 500
    assert "Test_Rate_Error" in response.json().get("detail", "")
