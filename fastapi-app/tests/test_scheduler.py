import sys
import types
from unittest.mock import MagicMock, patch
import logging

# Inject mock modules before scheduler triggers pdfplumber/cryptography chain
_mock_pdfplumber = types.ModuleType("pdfplumber")
sys.modules.setdefault("pdfplumber", _mock_pdfplumber)

_mock_pdfviewer = types.ModuleType("pdfviewer")
_mock_pdfviewer.find_pdf_urls = MagicMock(return_value=[])
_mock_pdfviewer.download_pdf = MagicMock(return_value=b"")
_mock_pdfviewer.extract_pdf_text = MagicMock(return_value="")
sys.modules.setdefault("pdfviewer", _mock_pdfviewer)

_mock_crawling_noti = types.ModuleType("crawling_noti")
_mock_crawling_noti.crawl_notices = MagicMock(return_value=5)
sys.modules["crawling_noti"] = _mock_crawling_noti

_mock_crawling_job = types.ModuleType("crawling_job")
_mock_crawling_job.crawl_jobs = MagicMock(return_value=10)
sys.modules["crawling_job"] = _mock_crawling_job

# scheduler may have been imported earlier with real modules; force re-import
sys.modules.pop("scheduler", None)

import pytest
from scheduler import noti_crawl, job_posting_crawl


class TestNotiCrawl:
    def setup_method(self):
        _mock_crawling_noti.crawl_notices.reset_mock()
        _mock_crawling_noti.crawl_notices.side_effect = None
        _mock_crawling_noti.crawl_notices.return_value = 5

    def test_calls_crawl_notices_with_page_count_2(self):
        noti_crawl()
        _mock_crawling_noti.crawl_notices.assert_called_once_with(page_count=2)

    def test_returns_none_on_success(self):
        _mock_crawling_noti.crawl_notices.return_value = 3
        result = noti_crawl()
        assert result is None

    def test_handles_exception_without_raising(self):
        _mock_crawling_noti.crawl_notices.side_effect = Exception("DB connection failed")
        noti_crawl()  # should not raise

    def test_logs_start_message(self, caplog):
        with caplog.at_level(logging.INFO, logger="scheduler"):
            noti_crawl()
        assert any("공지 크롤링 시작" in r.message for r in caplog.records)

    def test_logs_completion_count_on_success(self, caplog):
        _mock_crawling_noti.crawl_notices.return_value = 7
        with caplog.at_level(logging.INFO, logger="scheduler"):
            noti_crawl()
        assert any("7" in r.message for r in caplog.records)

    def test_logs_error_on_exception(self, caplog):
        _mock_crawling_noti.crawl_notices.side_effect = RuntimeError("timeout")
        with caplog.at_level(logging.ERROR, logger="scheduler"):
            noti_crawl()
        assert any("timeout" in r.message for r in caplog.records)


class TestJobPostingCrawl:
    def setup_method(self):
        _mock_crawling_job.crawl_jobs.reset_mock()
        _mock_crawling_job.crawl_jobs.side_effect = None
        _mock_crawling_job.crawl_jobs.return_value = 10

    def test_calls_crawl_jobs_with_page_count_3(self):
        job_posting_crawl()
        _mock_crawling_job.crawl_jobs.assert_called_once_with(page_count=3)

    def test_returns_none_on_success(self):
        _mock_crawling_job.crawl_jobs.return_value = 20
        result = job_posting_crawl()
        assert result is None

    def test_handles_exception_without_raising(self):
        _mock_crawling_job.crawl_jobs.side_effect = Exception("network error")
        job_posting_crawl()  # should not raise

    def test_logs_start_message(self, caplog):
        with caplog.at_level(logging.INFO, logger="scheduler"):
            job_posting_crawl()
        assert any("채용 크롤링 시작" in r.message for r in caplog.records)

    def test_logs_completion_count_on_success(self, caplog):
        _mock_crawling_job.crawl_jobs.return_value = 42
        with caplog.at_level(logging.INFO, logger="scheduler"):
            job_posting_crawl()
        assert any("42" in r.message for r in caplog.records)

    def test_logs_error_on_exception(self, caplog):
        _mock_crawling_job.crawl_jobs.side_effect = ValueError("parse failed")
        with caplog.at_level(logging.ERROR, logger="scheduler"):
            job_posting_crawl()
        assert any("parse failed" in r.message for r in caplog.records)
