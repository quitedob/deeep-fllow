# tests/adapters/test_dingtalk_adapter.py
# -*- coding: utf-8 -*-
import pytest
import logging # For caplog
from unittest.mock import MagicMock, patch

from src.adapters import dingtalk_adapter as dt_adapter
from src.config import settings

# Removed @patch.object decorator
def test_send_dingbot_text_no_library(capsys, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(dt_adapter, 'DingtalkChatbot', None) # Simulate library not installed via monkeypatch
    monkeypatch.setattr(dt_adapter, '_bot_initialized', False)
    monkeypatch.setattr(dt_adapter, 'bot', None)
    # DINGTALK_WEBHOOK can be anything or empty, the library check comes first
    # Patch directly in dt_adapter module
    monkeypatch.setattr(dt_adapter, "DINGTALK_WEBHOOK", "http://dummy.webhook")


    dt_adapter.send_dingbot_text("测试消息 no library")

    captured_print = capsys.readouterr().out
    assert "DINGTALK ADAPTER FALLBACK" in captured_print
    assert "测试消息 no library" in captured_print
    assert "DingtalkChatbot library is not installed" in caplog.text
    assert "DingtalkChatbot not available or not configured" in caplog.text

# Removed @patch.object decorator and mock_dingtalk_chatbot_class param
def test_send_dingbot_text_no_webhook(capsys, monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    mock_dingtalk_chatbot_constructor = MagicMock() # This will be used to mock the class
    monkeypatch.setattr(dt_adapter, 'DingtalkChatbot', mock_dingtalk_chatbot_constructor) # Simulate library IS installed

    monkeypatch.setattr(dt_adapter, '_bot_initialized', False)
    monkeypatch.setattr(dt_adapter, 'bot', None)
    # Patch directly in dt_adapter module
    monkeypatch.setattr(dt_adapter, "DINGTALK_WEBHOOK", "") # No webhook configured

    dt_adapter.send_dingbot_text("测试消息 no webhook")

    captured_print = capsys.readouterr().out
    assert "DINGTALK ADAPTER FALLBACK" in captured_print
    assert "测试消息 no webhook" in captured_print

    assert "DINGTALK_WEBHOOK not configured" in caplog.text # Log from _get_dingtalk_bot
    assert "DingtalkChatbot not available or not configured" in caplog.text # Log from send_dingbot_text
    mock_dingtalk_chatbot_constructor.assert_not_called() # Constructor should not be called

def test_send_dingbot_text_success_with_secret(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    mock_bot_instance = MagicMock()
    # This mock will be the DingtalkChatbot class itself
    mock_dingtalk_chatbot_constructor = MagicMock(return_value=mock_bot_instance)

    monkeypatch.setattr(dt_adapter, 'DingtalkChatbot', mock_dingtalk_chatbot_constructor)
    # Patch directly in dt_adapter module
    monkeypatch.setattr(dt_adapter, "DINGTALK_WEBHOOK", "https://mock.webhook.url/token")
    monkeypatch.setattr(dt_adapter, "DINGTALK_SECRET", "mock_secret")
    monkeypatch.setattr(dt_adapter, '_bot_initialized', False)
    monkeypatch.setattr(dt_adapter, 'bot', None)

    dt_adapter.send_dingbot_text("正常测试消息 with secret", at_mobiles=["123"], is_at_all=True)

    mock_dingtalk_chatbot_constructor.assert_called_once_with(
        "https://mock.webhook.url/token", secret="mock_secret"
    )
    mock_bot_instance.send_text.assert_called_once_with(
        msg="正常测试消息 with secret", at_mobiles=["123"], is_at_all=True
    )
    assert "消息发送成功" in caplog.text

def test_send_dingbot_text_success_without_secret(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    mock_bot_instance = MagicMock()
    mock_dingtalk_chatbot_constructor = MagicMock(return_value=mock_bot_instance)

    monkeypatch.setattr(dt_adapter, 'DingtalkChatbot', mock_dingtalk_chatbot_constructor)
    # Patch directly in dt_adapter module
    monkeypatch.setattr(dt_adapter, "DINGTALK_WEBHOOK", "https://another.mock.url")
    monkeypatch.setattr(dt_adapter, "DINGTALK_SECRET", "") # No secret
    monkeypatch.setattr(dt_adapter, '_bot_initialized', False)
    monkeypatch.setattr(dt_adapter, 'bot', None)

    dt_adapter.send_dingbot_text("正常测试消息 no secret")

    mock_dingtalk_chatbot_constructor.assert_called_once_with("https://another.mock.url")
    mock_bot_instance.send_text.assert_called_once_with(
        msg="正常测试消息 no secret", at_mobiles=[], is_at_all=False
    )
    assert "消息发送成功" in caplog.text


def test_get_dingtalk_bot_initialization_caching(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    mock_bot_instance = MagicMock()
    mock_dingtalk_chatbot_constructor = MagicMock(return_value=mock_bot_instance)

    monkeypatch.setattr(dt_adapter, 'DingtalkChatbot', mock_dingtalk_chatbot_constructor)
    # Patch directly in dt_adapter module
    monkeypatch.setattr(dt_adapter, "DINGTALK_WEBHOOK", "https://cachetest.mock.url")
    monkeypatch.setattr(dt_adapter, "DINGTALK_SECRET", "")

    monkeypatch.setattr(dt_adapter, '_bot_initialized', False)
    monkeypatch.setattr(dt_adapter, 'bot', None)

    bot1 = dt_adapter._get_dingtalk_bot()
    mock_dingtalk_chatbot_constructor.assert_called_once_with("https://cachetest.mock.url")
    assert "DingtalkChatbot initialized." in caplog.text
    assert bot1 is mock_bot_instance

    caplog.clear() # Clear logs before next call to see if "initialized" is logged again
    bot2 = dt_adapter._get_dingtalk_bot()
    mock_dingtalk_chatbot_constructor.assert_called_once() # Constructor still only called once due to caching
    assert "DingtalkChatbot initialized." not in caplog.text # No new initialization log
    assert bot2 is mock_bot_instance # Should return the same cached instance

def test_get_dingtalk_bot_init_fails_if_library_missing(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    monkeypatch.setattr(dt_adapter, 'DingtalkChatbot', None)
    # Patch directly in dt_adapter module
    monkeypatch.setattr(dt_adapter, "DINGTALK_WEBHOOK", "https://some.webhook") # Webhook is present
    monkeypatch.setattr(dt_adapter, '_bot_initialized', False)
    monkeypatch.setattr(dt_adapter, 'bot', None)

    bot_instance = dt_adapter._get_dingtalk_bot()
    assert bot_instance is None
    assert "DingtalkChatbot library is not installed" in caplog.text

def test_get_dingtalk_bot_init_fails_if_webhook_missing(monkeypatch, caplog):
    caplog.set_level(logging.WARNING) # Expecting a warning log
    # Assume DingtalkChatbot class exists (mock it)
    monkeypatch.setattr(dt_adapter, 'DingtalkChatbot', MagicMock())
    # Patch directly in dt_adapter module
    monkeypatch.setattr(dt_adapter, "DINGTALK_WEBHOOK", "") # Webhook is missing
    monkeypatch.setattr(dt_adapter, '_bot_initialized', False)
    monkeypatch.setattr(dt_adapter, 'bot', None)

    bot_instance = dt_adapter._get_dingtalk_bot()
    assert bot_instance is None
    assert "DINGTALK_WEBHOOK not configured" in caplog.text

if __name__ == '__main__':
    pytest.main([__file__])
