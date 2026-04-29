"""Tests for mailer.py — Gmail SMTP utility."""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch, call

import pytest

import mailer


class TestConfig:
    def test_defaults(self, monkeypatch):
        for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
                  "MAIL_FROM_NAME", "MAIL_FROM_EMAIL"):
            monkeypatch.delenv(k, raising=False)
        cfg = mailer._config()
        assert cfg["host"] == "smtp.gmail.com"
        assert cfg["port"] == 587
        assert cfg["user"] == ""
        assert cfg["password"] == ""
        assert cfg["from_name"] == "BoonPick"
        assert cfg["from_email"] == ""

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("SMTP_HOST", "mail.example.com")
        monkeypatch.setenv("SMTP_PORT", "465")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        monkeypatch.setenv("MAIL_FROM_NAME", "TestBot")
        monkeypatch.setenv("MAIL_FROM_EMAIL", "from@example.com")
        cfg = mailer._config()
        assert cfg["host"] == "mail.example.com"
        assert cfg["port"] == 465
        assert cfg["user"] == "user@example.com"
        assert cfg["password"] == "secret"
        assert cfg["from_name"] == "TestBot"
        assert cfg["from_email"] == "from@example.com"

    def test_from_email_defaults_to_smtp_user(self, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "sender@example.com")
        monkeypatch.delenv("MAIL_FROM_EMAIL", raising=False)
        cfg = mailer._config()
        assert cfg["from_email"] == "sender@example.com"


class TestSend:
    def _make_msg(self):
        msg = MIMEText("hello", _charset="utf-8")
        msg["Subject"] = "Test"
        return msg

    def test_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("SMTP_USER", raising=False)
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)
        msg = self._make_msg()
        with pytest.raises(RuntimeError, match="SMTP_USER"):
            mailer._send(msg, "to@example.com")

    def test_raises_with_empty_user(self, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "")
        monkeypatch.setenv("SMTP_PASSWORD", "pw")
        msg = self._make_msg()
        with pytest.raises(RuntimeError):
            mailer._send(msg, "to@example.com")

    def test_raises_with_empty_password(self, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "u@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "")
        msg = self._make_msg()
        with pytest.raises(RuntimeError):
            mailer._send(msg, "to@example.com")

    def test_calls_smtp_correctly(self, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "u@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "pw")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("MAIL_FROM_NAME", "Bot")
        monkeypatch.setenv("MAIL_FROM_EMAIL", "bot@example.com")

        mock_smtp_instance = MagicMock()
        mock_smtp_cm = MagicMock()
        mock_smtp_cm.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_cm.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP", return_value=mock_smtp_cm) as mock_smtp:
            msg = self._make_msg()
            mailer._send(msg, "to@example.com")

            mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=15)
            mock_smtp_instance.starttls.assert_called_once()
            mock_smtp_instance.login.assert_called_once_with("u@example.com", "pw")
            mock_smtp_instance.send_message.assert_called_once_with(msg)

    def test_sets_from_and_to_headers(self, monkeypatch):
        monkeypatch.setenv("SMTP_USER", "u@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "pw")
        monkeypatch.setenv("MAIL_FROM_NAME", "BoonPick")
        monkeypatch.setenv("MAIL_FROM_EMAIL", "bot@example.com")

        mock_smtp_instance = MagicMock()
        mock_smtp_cm = MagicMock()
        mock_smtp_cm.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_cm.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP", return_value=mock_smtp_cm):
            msg = self._make_msg()
            mailer._send(msg, "recipient@example.com")
            assert msg["To"] == "recipient@example.com"
            assert "bot@example.com" in msg["From"]


class TestSendVerificationCode:
    def test_sends_code_in_body(self, monkeypatch):
        sent = {}

        def fake_send(msg, to):
            sent["body"] = msg.get_payload(decode=True).decode("utf-8")
            sent["subject"] = msg["Subject"]
            sent["to"] = to

        with patch.object(mailer, "_send", side_effect=fake_send):
            mailer.send_verification_code("user@example.com", "123456")

        assert "123456" in sent["body"]
        assert "user@example.com" == sent["to"]
        assert "[BoonPick]" in sent["subject"]
        assert "인증코드" in sent["subject"]

    def test_default_expiry_in_body(self, monkeypatch):
        sent = {}

        def fake_send(msg, to):
            sent["body"] = msg.get_payload(decode=True).decode("utf-8")

        with patch.object(mailer, "_send", side_effect=fake_send):
            mailer.send_verification_code("u@ex.com", "ABC")

        assert "10분" in sent["body"]

    def test_custom_expiry(self):
        sent = {}

        def fake_send(msg, to):
            sent["body"] = msg.get_payload(decode=True).decode("utf-8")

        with patch.object(mailer, "_send", side_effect=fake_send):
            mailer.send_verification_code("u@ex.com", "XYZ", expires_minutes=30)

        assert "30분" in sent["body"]

    def test_propagates_send_error(self):
        with patch.object(mailer, "_send", side_effect=RuntimeError("SMTP error")):
            with pytest.raises(RuntimeError, match="SMTP error"):
                mailer.send_verification_code("u@ex.com", "999")


class TestSendNotificationEmail:
    def test_does_nothing_for_empty_items(self):
        with patch.object(mailer, "_send") as mock_send:
            mailer.send_notification_email("u@ex.com", [])
            mock_send.assert_not_called()

    def test_sends_for_nonempty_items(self):
        items = [
            {"title": "공고1", "category_label": "채용공고", "source": "sogang_job",
             "url": "http://ex.com/1", "summary": "요약1", "score": 80},
        ]
        sent = {}

        def fake_send(msg, to):
            sent["body"] = msg.get_payload(decode=True).decode("utf-8")
            sent["subject"] = msg["Subject"]
            sent["to"] = to

        with patch.object(mailer, "_send", side_effect=fake_send):
            mailer.send_notification_email("user@example.com", items)

        assert sent["to"] == "user@example.com"
        assert "공고1" in sent["body"]
        assert "80%" in sent["body"]
        assert "(1건)" in sent["subject"]

    def test_subject_reflects_count(self):
        items = [
            {"title": f"항목{i}", "category_label": "공지", "source": "sogang_notice",
             "url": f"http://ex.com/{i}", "summary": "s", "score": None}
            for i in range(5)
        ]
        sent = {}

        def fake_send(msg, to):
            sent["subject"] = msg["Subject"]

        with patch.object(mailer, "_send", side_effect=fake_send):
            mailer.send_notification_email("u@ex.com", items)

        assert "(5건)" in sent["subject"]

    def test_no_score_when_none(self):
        items = [
            {"title": "장학금", "category_label": "장학금공지", "source": "sogang_scholarship",
             "url": "http://ex.com", "summary": "장학", "score": None},
        ]
        sent = {}

        def fake_send(msg, to):
            sent["body"] = msg.get_payload(decode=True).decode("utf-8")

        with patch.object(mailer, "_send", side_effect=fake_send):
            mailer.send_notification_email("u@ex.com", items)

        assert "%" not in sent["body"] or "매칭" not in sent["body"]

    def test_multiple_items_all_in_body(self):
        items = [
            {"title": f"공고{i}", "category_label": "채용공고", "source": "sogang_job",
             "url": f"http://ex.com/{i}", "summary": f"요약{i}", "score": i * 10}
            for i in range(1, 4)
        ]
        sent = {}

        def fake_send(msg, to):
            sent["body"] = msg.get_payload(decode=True).decode("utf-8")

        with patch.object(mailer, "_send", side_effect=fake_send):
            mailer.send_notification_email("u@ex.com", items)

        for i in range(1, 4):
            assert f"공고{i}" in sent["body"]
