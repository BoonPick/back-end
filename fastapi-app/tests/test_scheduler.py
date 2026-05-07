import sys
import types
import logging
from unittest.mock import MagicMock

import pytest

# Safe stubs — only inject if the real library is not loadable.
# We MUST NOT touch sys.modules for crawling_noti, crawling_job, or notifier;
# doing so pollutes the rest of the pytest session and breaks unrelated tests.
sys.modules.setdefault("pdfplumber", types.ModuleType("pdfplumber"))

if "pdfviewer" not in sys.modules:
    _pdfviewer_stub = types.ModuleType("pdfviewer")
    _pdfviewer_stub.find_pdf_urls = MagicMock(return_value=[])
    _pdfviewer_stub.download_pdf = MagicMock(return_value=b"")
    _pdfviewer_stub.extract_pdf_text = MagicMock(return_value={"pages": [], "tables": []})
    sys.modules["pdfviewer"] = _pdfviewer_stub

from scheduler import noti_crawl, job_posting_crawl, notification_batch  # noqa: E402


class TestNotiCrawl:
    def test_calls_crawl_notices_with_page_count_2(self, mocker):
        mock = mocker.patch("scheduler.crawl_notices", return_value=5)
        noti_crawl()
        mock.assert_called_once_with(page_count=2)

    def test_returns_none_on_success(self, mocker):
        mocker.patch("scheduler.crawl_notices", return_value=3)
        assert noti_crawl() is None

    def test_handles_exception_without_raising(self, mocker):
        mocker.patch("scheduler.crawl_notices", side_effect=Exception("DB connection failed"))
        noti_crawl()  # must not raise

    def test_logs_start_message(self, mocker, caplog):
        mocker.patch("scheduler.crawl_notices", return_value=0)
        with caplog.at_level(logging.INFO, logger="scheduler"):
            noti_crawl()
        assert any("공지 크롤링 시작" in r.message for r in caplog.records)

    def test_logs_completion_count_on_success(self, mocker, caplog):
        mocker.patch("scheduler.crawl_notices", return_value=7)
        with caplog.at_level(logging.INFO, logger="scheduler"):
            noti_crawl()
        assert any("7" in r.message for r in caplog.records)

    def test_logs_error_on_exception(self, mocker, caplog):
        mocker.patch("scheduler.crawl_notices", side_effect=RuntimeError("timeout"))
        with caplog.at_level(logging.ERROR, logger="scheduler"):
            noti_crawl()
        assert any("timeout" in r.message for r in caplog.records)


class TestJobPostingCrawl:
    def test_calls_crawl_jobs_with_page_count_3(self, mocker):
        mock = mocker.patch("scheduler.crawl_jobs", return_value=10)
        job_posting_crawl()
        mock.assert_called_once_with(page_count=3)

    def test_returns_none_on_success(self, mocker):
        mocker.patch("scheduler.crawl_jobs", return_value=20)
        assert job_posting_crawl() is None

    def test_handles_exception_without_raising(self, mocker):
        mocker.patch("scheduler.crawl_jobs", side_effect=Exception("network error"))
        job_posting_crawl()  # must not raise

    def test_logs_start_message(self, mocker, caplog):
        mocker.patch("scheduler.crawl_jobs", return_value=0)
        with caplog.at_level(logging.INFO, logger="scheduler"):
            job_posting_crawl()
        assert any("채용 크롤링 시작" in r.message for r in caplog.records)

    def test_logs_completion_count_on_success(self, mocker, caplog):
        mocker.patch("scheduler.crawl_jobs", return_value=42)
        with caplog.at_level(logging.INFO, logger="scheduler"):
            job_posting_crawl()
        assert any("42" in r.message for r in caplog.records)

    def test_logs_error_on_exception(self, mocker, caplog):
        mocker.patch("scheduler.crawl_jobs", side_effect=ValueError("parse failed"))
        with caplog.at_level(logging.ERROR, logger="scheduler"):
            job_posting_crawl()
        assert any("parse failed" in r.message for r in caplog.records)


# ── auto-generated: notification_batch ──
class TestNotificationBatch:
    def test_calls_notify_new_items_for_all_users(self, mocker):
        mock = mocker.patch("scheduler.notify_new_items_for_all_users", return_value=3)
        notification_batch()
        mock.assert_called_once_with()

    def test_returns_none_on_success(self, mocker):
        mocker.patch("scheduler.notify_new_items_for_all_users", return_value=3)
        assert notification_batch() is None

    def test_logs_completion_with_sent_count_on_success(self, mocker, caplog):
        mocker.patch("scheduler.notify_new_items_for_all_users", return_value=5)
        with caplog.at_level(logging.INFO, logger="scheduler"):
            notification_batch()
        assert any("5" in r.message for r in caplog.records)

    def test_exception_is_caught_and_not_reraised(self, mocker):
        mocker.patch("scheduler.notify_new_items_for_all_users", side_effect=RuntimeError("smtp error"))
        notification_batch()  # must not raise

    def test_exception_is_logged_as_error(self, mocker, caplog):
        mocker.patch("scheduler.notify_new_items_for_all_users", side_effect=Exception("connection refused"))
        with caplog.at_level(logging.ERROR, logger="scheduler"):
            notification_batch()
        assert any("connection refused" in r.message for r in caplog.records)
