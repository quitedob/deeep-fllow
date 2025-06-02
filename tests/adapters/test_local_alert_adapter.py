# tests/adapters/test_local_alert_adapter.py
# -*- coding: utf-8 -*-
"""
LocalAlertAdapter 单元测试：仅验证在 SMTP 配置不完整时会打印 Warning 日志，
以及在配置完整时尝试调用 smtplib 发送且不抛异常（可使用 monkeypatch 替换 smtplib.SMTP）。
"""

import pytest
import smtplib # For monkeypatching and for smtplib.SMTPException
import logging # For caplog
from unittest.mock import MagicMock, patch

# Import the module itself with an alias
from src.adapters import local_alert_adapter as local_alert_adapter_mod
# Keep LocalAlertAdapter for direct use if needed, or access via local_alert_adapter_mod.LocalAlertAdapter
from src.adapters.local_alert_adapter import LocalAlertAdapter
# Settings import is not strictly needed if we patch module-level attributes directly in local_alert_adapter_mod
# from src.config import settings

# -----------------------------
# 测试 SMTP 配置不全时，仅打印 Warning，不抛异常
# -----------------------------
def test_send_email_skipped_due_to_incomplete_settings(caplog, monkeypatch):
    # Patch directly in the local_alert_adapter module's namespace
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_SERVER", "")
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_PASSWORD", "password")
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_PORT", 587)


    caplog.set_level(logging.WARNING)

    LocalAlertAdapter.send_email("TestSubject", "TestBody", ["a@b.com"])

    assert "SMTP not fully configured or no recipients" in caplog.text
    assert "TestSubject" in caplog.text

def test_send_email_skipped_due_to_no_recipients(caplog, monkeypatch):
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_SERVER", "smtp.example.com")
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_PORT", 587)
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_PASSWORD", "password")
    caplog.set_level(logging.WARNING)

    local_alert_adapter_mod.LocalAlertAdapter.send_email("TestSubject", "TestBody", []) # Empty recipient list
    assert "SMTP not fully configured or no recipients" in caplog.text


# -----------------------------
# 测试 send_email 调用 smtplib.SMTP，不抛异常
# -----------------------------
def test_send_email_success_with_mocked_smtp(monkeypatch, caplog):
    # Patch directly in the local_alert_adapter module's namespace
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_SERVER", "smtp.example.com")
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_PORT", 587)
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(local_alert_adapter_mod, "SMTP_PASSWORD", "correct_password")
    caplog.set_level(logging.INFO)

    class FakeSmtpConnection:
        def __init__(self, server, port, timeout):
            self.server = server
            self.port = port
            self.timeout = timeout
            self.has_extn_called_for_starttls = False
            self.starttls_called = False
            self.login_called_with = None
            self.sendmail_called_with = None
            self.ehlo_called_count = 0

        def ehlo(self):
            self.ehlo_called_count += 1

        def has_extn(self, ext_name):
            if ext_name.lower() == 'starttls':
                if not self.has_extn_called_for_starttls:
                    self.has_extn_called_for_starttls = True
                    return True
            return False

        def starttls(self):
            self.starttls_called = True

        def login(self, user, password):
            self.login_called_with = (user, password)

        def sendmail(self, from_addr, to_addrs, msg_string):
            self.sendmail_called_with = (from_addr, to_addrs, msg_string)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    # This will hold the instance of FakeSmtpConnection created during the test
    # Needs to be a list or dict to be modifiable by inner function in Python 2/3 non-local way
    # Or, make mock_smtp_instance an attribute of the test class if this were unittest.TestCase
    # For pytest, a simple mutable list wrapper works to share the instance.
    smtp_instance_holder = {}

    def mock_smtp_constructor(server, port, timeout=None):
        instance = FakeSmtpConnection(server, port, timeout)
        smtp_instance_holder['instance'] = instance
        return instance

    monkeypatch.setattr(smtplib, "SMTP", mock_smtp_constructor)

    LocalAlertAdapter.send_email("SubjectOK", "BodyOK", ["x@y.com"])

    mock_smtp_instance = smtp_instance_holder.get('instance')
    assert mock_smtp_instance is not None, "FakeSmtpConnection instance was not created"

    assert "Email alert sent" in caplog.text
    assert mock_smtp_instance.ehlo_called_count >= 1
    assert mock_smtp_instance.starttls_called == True
    # Assert against the values patched into local_alert_adapter_mod module
    assert mock_smtp_instance.login_called_with == (local_alert_adapter_mod.SMTP_USER, local_alert_adapter_mod.SMTP_PASSWORD)
    assert mock_smtp_instance.sendmail_called_with is not None
    assert mock_smtp_instance.sendmail_called_with[0] == local_alert_adapter_mod.SMTP_USER
    assert mock_smtp_instance.sendmail_called_with[1] == ["x@y.com"]
    assert "Subject: SubjectOK" in mock_smtp_instance.sendmail_called_with[2]


# -----------------------------
# 测试 notify() 方法调用 send_email with hardcoded recipient
# -----------------------------
@patch.object(local_alert_adapter_mod.LocalAlertAdapter, 'send_email')
def test_notify_calls_send_email_with_hardcoded_recipient(mock_send_email_method, caplog):
    caplog.set_level(logging.INFO)
    local_alert_adapter_mod.LocalAlertAdapter.notify("NSubj", "NBody")

    mock_send_email_method.assert_called_once_with("NSubj", "NBody", ["admin@example.com"])
    assert "LocalAlertAdapter attempting to notify" in caplog.text

if __name__ == '__main__':
    pytest.main([__file__])
