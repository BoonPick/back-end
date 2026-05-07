import sys
from unittest.mock import MagicMock

# pdfplumber (and its broken cffi/cryptography chain) is not available in this
# environment.  Stub it out before any source module is imported so that
# collection does not crash.
sys.modules.setdefault('pdfplumber', MagicMock())

import pytest
from datetime import datetime
from crawling_noti import extract_category_from_title, parse_notice_date
import crawling_noti as _crawling_noti_mod


class TestExtractCategoryFromTitle:
    def test_extracts_bracket_category(self):
        category, title = extract_category_from_title("[장학] 2025년 장학생 모집")
        assert category == "장학"
        assert title == "2025년 장학생 모집"

    def test_strips_whitespace(self):
        category, title = extract_category_from_title("[  취업  ]  공고 안내")
        assert category == "취업"
        assert title == "공고 안내"

    def test_no_bracket_returns_empty_category(self):
        category, title = extract_category_from_title("일반 공지사항")
        assert category == ""
        assert title == "일반 공지사항"

    def test_empty_string(self):
        category, title = extract_category_from_title("")
        assert category == ""
        assert title == ""

    def test_only_bracket_no_title(self):
        category, title = extract_category_from_title("[카테고리]")
        assert category == "카테고리"
        assert title == ""


class TestParseNoticeDate:
    def test_parses_regdate_14digit(self):
        notice = {"regDate": "20260424132703"}
        result = parse_notice_date(notice)
        assert result == datetime(2026, 4, 24, 13, 27, 3)

    def test_parses_create_date_iso(self):
        notice = {"createDate": "2026-04-24 13:27:03"}
        result = parse_notice_date(notice)
        assert result == datetime(2026, 4, 24, 13, 27, 3)

    def test_parses_iso_t_format(self):
        notice = {"createDate": "2026-04-24T13:27:03"}
        result = parse_notice_date(notice)
        assert result == datetime(2026, 4, 24, 13, 27, 3)

    def test_parses_date_only(self):
        notice = {"registDate": "2026-04-24"}
        result = parse_notice_date(notice)
        assert result == datetime(2026, 4, 24)

    def test_tries_multiple_fields_in_order(self):
        notice = {"modifyDate": "2026-01-01", "createDate": "2025-01-01"}
        result = parse_notice_date(notice)
        assert result == datetime(2025, 1, 1)

    def test_returns_none_when_no_date_field(self):
        assert parse_notice_date({}) is None

    def test_returns_none_when_unparseable(self):
        assert parse_notice_date({"createDate": "not-a-date"}) is None


# ── auto-generated: get_db_connection ──
import mysql.connector
from crawling_noti import get_db_connection, DB_CONFIG


class TestGetDbConnection:
    def test_calls_connect_with_db_config(self, mocker):
        mock_connect = mocker.patch("mysql.connector.connect")
        get_db_connection()
        mock_connect.assert_called_once_with(**DB_CONFIG)

    def test_returns_connection_object(self, mocker):
        mock_conn = MagicMock()
        mocker.patch("mysql.connector.connect", return_value=mock_conn)
        result = get_db_connection()
        assert result is mock_conn


# ── auto-generated: notice_exists ──
from crawling_noti import notice_exists


class TestNoticeExists:
    def test_returns_true_when_row_found(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        result = notice_exists(mock_cursor, "https://example.com/notice/1")
        assert result is True
        mock_cursor.execute.assert_called_once_with(
            "SELECT id FROM contents WHERE url = %s",
            ("https://example.com/notice/1",),
        )

    def test_returns_false_when_no_row(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        result = notice_exists(mock_cursor, "https://example.com/notice/999")
        assert result is False

    def test_execute_called_with_correct_url(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        url = "https://www.sogang.ac.kr/ko/detail/42?bbsConfigFk=2"
        notice_exists(mock_cursor, url)
        mock_cursor.execute.assert_called_once_with(
            "SELECT id FROM contents WHERE url = %s", (url,)
        )


# ── auto-generated: save_notice ──
from crawling_noti import save_notice


class TestSaveNotice:
    def test_with_posted_at_executes_insert_with_date(self):
        mock_cursor = MagicMock()
        posted_at = datetime(2026, 4, 24, 13, 27, 3)
        save_notice(
            mock_cursor,
            title="Test Title",
            source_name="sogang_notice",
            category="장학",
            url="https://www.sogang.ac.kr/ko/detail/1?bbsConfigFk=2",
            raw_content="Some content",
            posted_at=posted_at,
        )
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        # The SQL must include the 6-parameter VALUES row (includes posted_at slot)
        assert "INSERT INTO contents" in sql
        assert "%s, %s, %s, %s, %s, %s, NOW()" in sql
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert params == (
            "Test Title",
            "sogang_notice",
            "장학",
            "https://www.sogang.ac.kr/ko/detail/1?bbsConfigFk=2",
            "Some content",
            posted_at,
        )

    def test_without_posted_at_executes_insert_with_now(self):
        mock_cursor = MagicMock()
        save_notice(
            mock_cursor,
            title="No Date Title",
            source_name="sogang_scholarship",
            category="",
            url="https://www.sogang.ac.kr/ko/detail/2?bbsConfigFk=141",
            raw_content="Other content",
            posted_at=None,
        )
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        # The SQL must use NOW() for created_at (5-param tuple, no posted_at)
        assert "INSERT INTO contents" in sql
        assert "%s, %s, %s, %s, %s, NOW(), NOW()" in sql
        assert "ON DUPLICATE KEY UPDATE" in sql
        assert params == (
            "No Date Title",
            "sogang_scholarship",
            "",
            "https://www.sogang.ac.kr/ko/detail/2?bbsConfigFk=141",
            "Other content",
        )

    def test_posted_at_none_is_default(self):
        mock_cursor = MagicMock()
        # Call without keyword posted_at to confirm default=None path
        save_notice(mock_cursor, "T", "src", "cat", "http://u", "body")
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "NOW(), NOW()" in sql


# ── auto-generated: crawl_notices ──
import json
from unittest.mock import call, patch
from crawling_noti import crawl_notices


class TestCrawlNotices:
    """Helper that builds a minimal list-API JSON response."""

    @staticmethod
    def _list_response(board_cfg, notices):
        return {"data": {"list": notices}}

    @staticmethod
    def _detail_response(content_html="<p>Detail body</p>"):
        return {"data": {"content": content_html, "createDate": "2026-04-24 13:27:03"}}

    def _make_notice(self, pk=101, title="[장학] Test Notice", category=""):
        return {
            "pkId": pk,
            "title": title,
            "category": category,
            "createDate": "2026-04-24 13:27:03",
        }

    def test_saves_new_notice_returns_correct_count(self, mocker):
        """One board page with one new notice → saved_count == 1 per board."""
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        notice = self._make_notice(pk=101)
        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response(None, [notice])

        detail_resp = MagicMock()
        detail_resp.json.return_value = self._detail_response()

        # requests.get: first call → list, second call → detail, repeat for second board
        notice2 = self._make_notice(pk=201, title="Scholarship Notice")
        list_resp2 = MagicMock()
        list_resp2.json.return_value = self._list_response(None, [notice2])

        detail_resp2 = MagicMock()
        detail_resp2.json.return_value = self._detail_response()

        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.side_effect = [list_resp, detail_resp, list_resp2, detail_resp2]
        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=False)
        mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=[])

        result = crawl_notices(page_count=1)
        assert result == 2

    def test_empty_data_returns_zero_saved(self, mocker):
        """API returns no list data → nothing saved."""
        mock_conn = MagicMock()
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}
        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.return_value = empty_resp
        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=False)
        mock_save = mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=[])

        result = crawl_notices(page_count=1)
        assert result == 0
        mock_save.assert_not_called()

    def test_notice_already_exists_is_skipped(self, mocker):
        """notice_exists returns True → save_notice never called."""
        mock_conn = MagicMock()
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        notice = self._make_notice(pk=301)
        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response(None, [notice])

        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.return_value = list_resp
        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=True)
        mock_save = mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=[])

        result = crawl_notices(page_count=1)
        assert result == 0
        mock_save.assert_not_called()

    def test_conn_commit_called_per_saved_notice(self, mocker):
        """conn.commit() must be called once for each saved notice."""
        mock_conn = MagicMock()
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        notice = self._make_notice(pk=401)
        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response(None, [notice])

        # Second board returns empty
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}

        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.side_effect = [list_resp, MagicMock(**{"json.return_value": self._detail_response()}), empty_resp]
        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=False)
        mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=[])

        crawl_notices(page_count=1)
        assert mock_conn.commit.call_count == 1

    def test_cursor_and_conn_closed_after_crawl(self, mocker):
        """cursor.close() and conn.close() are always called (finally block)."""
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}
        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.return_value = empty_resp
        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=False)
        mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=[])

        crawl_notices(page_count=1)
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_save_notice_called_with_correct_args(self, mocker):
        """Verify save_notice receives the expected arguments for a known notice."""
        mock_conn = MagicMock()
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        notice = {
            "pkId": 501,
            "title": "[장학] 2026 장학생 모집",
            "category": "",
            "createDate": "2026-04-24 13:27:03",
        }
        list_resp = MagicMock()
        list_resp.json.return_value = {"data": {"list": [notice]}}

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "data": {"content": "<p>Hello</p>", "createDate": "2026-04-24 13:27:03"}
        }

        # Second board → empty
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}

        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.side_effect = [list_resp, detail_resp, empty_resp]
        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=False)
        mock_save = mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=[])

        crawl_notices(page_count=1)

        assert mock_save.call_count == 1
        args, kwargs = mock_save.call_args
        # args: (cursor, title, source_name, category, url, raw_content)
        assert args[1] == "2026 장학생 모집"          # title stripped of [장학]
        assert args[2] == "sogang_notice"             # first board
        assert args[3] == "장학"                       # category extracted from title
        assert "501" in args[4]                        # url contains pkId
        assert kwargs.get("posted_at") == datetime(2026, 4, 24, 13, 27, 3)


# ── auto-generated: crawl_notices_pdf_branch ──
import os


class TestCrawlNoticesPdfBranch:
    """Tests for the PDF handling branch inside crawl_notices() (lines 172-193)."""

    @staticmethod
    def _list_response(notices):
        return {"data": {"list": notices}}

    @staticmethod
    def _detail_response(content_html="<p>Notice body</p>"):
        return {"data": {"content": content_html, "createDate": "2026-04-24 13:27:03"}}

    def _make_notice(self, pk=601, title="[공지] PDF Notice"):
        return {
            "pkId": pk,
            "title": title,
            "category": "",
            "createDate": "2026-04-24 13:27:03",
        }

    def _setup_mocks(self, mocker, notice, pdf_urls, extract_result, detail_html="<p>Body</p>"):
        """Wire up all mocks and return (mock_requests, mock_download, mock_extract, mock_save)."""
        mock_conn = MagicMock()
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response([notice])

        detail_resp = MagicMock()
        detail_resp.json.return_value = self._detail_response(detail_html)

        # Second board returns empty so only one board processes PDFs
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}

        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.side_effect = [list_resp, detail_resp, empty_resp]

        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=False)
        mock_save = mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=pdf_urls)
        mock_download = mocker.patch.object(_crawling_noti_mod, 'download_pdf')
        mock_extract = mocker.patch.object(_crawling_noti_mod, 'extract_pdf_text', return_value=extract_result)

        return mock_requests, mock_download, mock_extract, mock_save

    def test_download_and_extract_called_for_each_pdf_url(self, mocker):
        """When find_pdf_urls returns URLs, download_pdf and extract_pdf_text are called once per URL."""
        notice = self._make_notice(pk=601)
        pdf_urls = ["https://example.com/file1.pdf", "https://example.com/file2.pdf"]
        extract_result = {"pages": [], "tables": []}

        _, mock_download, mock_extract, _ = self._setup_mocks(
            mocker, notice, pdf_urls, extract_result
        )

        crawl_notices(page_count=1)

        assert mock_download.call_count == 2
        assert mock_extract.call_count == 2
        # Verify the temp path pattern: temp_{pkId}_{idx}.pdf
        mock_download.assert_any_call("https://example.com/file1.pdf", "temp_601_1.pdf")
        mock_download.assert_any_call("https://example.com/file2.pdf", "temp_601_2.pdf")

    def test_pdf_text_and_table_content_included_in_save_notice(self, mocker):
        """Page text and table rows from extract_pdf_text are included in raw_content passed to save_notice."""
        notice = self._make_notice(pk=602)
        pdf_urls = ["https://example.com/report.pdf"]
        extract_result = {
            "pages": [{"page": 1, "text": "Important PDF text"}],
            "tables": [{"page": 2, "data": [["Col A", "Col B"], ["Val 1", "Val 2"]]}],
        }

        _, _, _, mock_save = self._setup_mocks(mocker, notice, pdf_urls, extract_result)

        crawl_notices(page_count=1)

        assert mock_save.call_count == 1
        args, _ = mock_save.call_args
        raw_content = args[5]  # positional: cursor, title, source_name, category, url, raw_content
        assert "Important PDF text" in raw_content
        assert "[PDF 1 - Page 1]" in raw_content
        assert "Col A" in raw_content
        assert "[PDF 1 - Table Page 2]" in raw_content

    def test_pdf_exception_handled_gracefully_no_raise(self, mocker):
        """When download_pdf raises, the error message is appended to content and no exception propagates."""
        notice = self._make_notice(pk=603)
        pdf_urls = ["https://example.com/broken.pdf"]

        mock_conn = MagicMock()
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response([notice])
        detail_resp = MagicMock()
        detail_resp.json.return_value = self._detail_response("<p>Body</p>")
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}

        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.side_effect = [list_resp, detail_resp, empty_resp]

        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=False)
        mock_save = mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=pdf_urls)
        mocker.patch.object(_crawling_noti_mod, 'download_pdf', side_effect=RuntimeError("connection refused"))
        mocker.patch.object(_crawling_noti_mod, 'extract_pdf_text')

        # Must not raise
        result = crawl_notices(page_count=1)

        # Notice is still saved despite the PDF error
        assert mock_save.call_count == 1
        args, _ = mock_save.call_args
        raw_content = args[5]
        assert "[PDF 오류:" in raw_content
        assert "connection refused" in raw_content

    def test_pdf_temp_file_cleaned_up_in_finally(self, mocker):
        """The temp PDF file is removed in the finally block even when extraction succeeds."""
        notice = self._make_notice(pk=604)
        pdf_urls = ["https://example.com/clean.pdf"]
        extract_result = {"pages": [{"page": 1, "text": "page text"}], "tables": []}

        mock_conn = MagicMock()
        mocker.patch.object(_crawling_noti_mod, 'get_db_connection', return_value=mock_conn)

        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response([notice])
        detail_resp = MagicMock()
        detail_resp.json.return_value = self._detail_response("<p>Body</p>")
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}

        mock_requests = mocker.patch.object(_crawling_noti_mod, 'requests')
        mock_requests.get.side_effect = [list_resp, detail_resp, empty_resp]

        mocker.patch.object(_crawling_noti_mod, 'notice_exists', return_value=False)
        mocker.patch.object(_crawling_noti_mod, 'save_notice')
        mocker.patch.object(_crawling_noti_mod, 'find_pdf_urls', return_value=pdf_urls)
        mocker.patch.object(_crawling_noti_mod, 'download_pdf')
        mocker.patch.object(_crawling_noti_mod, 'extract_pdf_text', return_value=extract_result)

        # Simulate temp file existing so the finally branch actually calls os.remove
        mock_os_path_exists = mocker.patch.object(_crawling_noti_mod.os.path, 'exists', return_value=True)
        mock_os_remove = mocker.patch.object(_crawling_noti_mod.os, 'remove')

        crawl_notices(page_count=1)

        expected_pdf_path = "temp_604_1.pdf"
        mock_os_path_exists.assert_any_call(expected_pdf_path)
        mock_os_remove.assert_called_once_with(expected_pdf_path)
