import sys
import types
import logging
import runpy
from unittest.mock import MagicMock, call, patch

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


# ── auto-generated: __main__ ──
class TestMainBlock:
    """Tests for the if __name__ == '__main__' block in scheduler.py.

    Strategy: patch apscheduler.schedulers.blocking.BlockingScheduler at the
    source (the apscheduler module itself) BEFORE calling runpy.run_path so
    that when scheduler.py executes `from apscheduler.schedulers.blocking import
    BlockingScheduler` inside its own fresh globals, it picks up our mock.
    """

    SCHEDULER_PATH = "/tmp/back-end/fastapi-app/scheduler.py"
    PATCH_TARGET = "apscheduler.schedulers.blocking.BlockingScheduler"

    def _run_main(self, mock_cls):
        """Execute the __main__ block via runpy with BlockingScheduler mocked."""
        runpy.run_path(
            self.SCHEDULER_PATH,
            init_globals={"__name__": "__main__"},
            run_name="__main__",
        )

    def test_blocking_scheduler_is_instantiated(self, mocker):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.return_value = None
        with patch(self.PATCH_TARGET, mock_cls):
            self._run_main(mock_cls)
        mock_cls.assert_called_once_with()

    def test_three_jobs_are_added(self, mocker):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.return_value = None
        with patch(self.PATCH_TARGET, mock_cls):
            self._run_main(mock_cls)
        assert mock_instance.add_job.call_count == 3

    def test_noti_crawl_job_configuration(self, mocker):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.return_value = None
        with patch(self.PATCH_TARGET, mock_cls):
            self._run_main(mock_cls)

        calls = mock_instance.add_job.call_args_list
        # First job must be noti_crawl
        first_call = calls[0]
        args, kwargs = first_call
        # The job function may be passed positionally or as keyword
        func = args[0] if args else kwargs.get("func")
        assert func.__name__ == "noti_crawl"
        assert kwargs.get("trigger") == "cron"
        assert kwargs.get("hour") == 2
        assert kwargs.get("minute") == 15
        assert kwargs.get("id") == "daily_noti_crawl"

    def test_job_posting_crawl_job_configuration(self, mocker):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.return_value = None
        with patch(self.PATCH_TARGET, mock_cls):
            self._run_main(mock_cls)

        calls = mock_instance.add_job.call_args_list
        second_call = calls[1]
        args, kwargs = second_call
        func = args[0] if args else kwargs.get("func")
        assert func.__name__ == "job_posting_crawl"
        assert kwargs.get("trigger") == "cron"
        assert kwargs.get("hour") == 2
        assert kwargs.get("minute") == 30
        assert kwargs.get("id") == "daily_job_crawl"

    def test_notification_batch_job_configuration(self, mocker):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.return_value = None
        with patch(self.PATCH_TARGET, mock_cls):
            self._run_main(mock_cls)

        calls = mock_instance.add_job.call_args_list
        third_call = calls[2]
        args, kwargs = third_call
        func = args[0] if args else kwargs.get("func")
        assert func.__name__ == "notification_batch"
        assert kwargs.get("trigger") == "cron"
        assert kwargs.get("hour") == 3
        assert kwargs.get("minute") == 0
        assert kwargs.get("id") == "daily_notification_batch"

    def test_all_jobs_use_kst_timezone(self, mocker):
        from zoneinfo import ZoneInfo
        kst = ZoneInfo("Asia/Seoul")

        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.return_value = None
        with patch(self.PATCH_TARGET, mock_cls):
            self._run_main(mock_cls)

        for job_call in mock_instance.add_job.call_args_list:
            _, kwargs = job_call
            assert kwargs.get("timezone") == kst, (
                f"Expected KST timezone for job {kwargs.get('id')}"
            )

    def test_scheduler_start_is_called(self, mocker):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.return_value = None
        with patch(self.PATCH_TARGET, mock_cls):
            self._run_main(mock_cls)
        mock_instance.start.assert_called_once_with()

    def test_keyboard_interrupt_is_handled_gracefully(self, mocker):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.side_effect = KeyboardInterrupt
        with patch(self.PATCH_TARGET, mock_cls):
            # Should not propagate — the __main__ block catches KeyboardInterrupt
            self._run_main(mock_cls)  # must not raise

    def test_system_exit_is_handled_gracefully(self, mocker):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.side_effect = SystemExit
        with patch(self.PATCH_TARGET, mock_cls):
            # Should not propagate — the __main__ block catches SystemExit
            self._run_main(mock_cls)  # must not raise

    def test_logs_scheduler_start_message(self, mocker, caplog):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.return_value = None
        with patch(self.PATCH_TARGET, mock_cls):
            with caplog.at_level(logging.INFO):
                self._run_main(mock_cls)
        messages = " ".join(r.message for r in caplog.records)
        assert "스케줄러 시작" in messages

    def test_logs_scheduler_shutdown_on_keyboard_interrupt(self, mocker, caplog):
        mock_cls = mocker.MagicMock()
        mock_instance = mock_cls.return_value
        mock_instance.start.side_effect = KeyboardInterrupt
        with patch(self.PATCH_TARGET, mock_cls):
            with caplog.at_level(logging.INFO):
                self._run_main(mock_cls)
        messages = " ".join(r.message for r in caplog.records)
        assert "스케줄러 종료" in messages
