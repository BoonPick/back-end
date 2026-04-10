"""
scheduler.py 테스트
"""

import pytest
from unittest.mock import patch, MagicMock

from scheduler import job_crawl


class TestJobCrawl:
    def test_calls_crawl_notices_with_page_count_2(self):
        with patch("scheduler.crawl_notices", return_value=5) as mock_crawl:
            job_crawl()

        mock_crawl.assert_called_once_with(page_count=2)

    def test_logs_saved_count_on_success(self, caplog):
        import logging
        with patch("scheduler.crawl_notices", return_value=3):
            with caplog.at_level(logging.INFO, logger="scheduler"):
                job_crawl()

        assert "3" in caplog.text

    def test_logs_error_on_exception(self, caplog):
        import logging
        with patch("scheduler.crawl_notices", side_effect=Exception("크롤링 실패")):
            with caplog.at_level(logging.ERROR, logger="scheduler"):
                job_crawl()

        assert "크롤링 실패" in caplog.text

    def test_does_not_raise_on_exception(self):
        """crawl_notices 예외가 발생해도 job_crawl은 터지지 않음"""
        with patch("scheduler.crawl_notices", side_effect=RuntimeError("치명적 오류")):
            job_crawl()  # 예외 전파 없음

    def test_zero_saved_count_logged(self, caplog):
        import logging
        with patch("scheduler.crawl_notices", return_value=0):
            with caplog.at_level(logging.INFO, logger="scheduler"):
                job_crawl()

        assert "0" in caplog.text
