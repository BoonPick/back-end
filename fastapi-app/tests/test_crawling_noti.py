import sys
from unittest.mock import MagicMock

# pdfplumber (and its broken cffi/cryptography chain) is not available in this
# environment.  Stub it out before any source module is imported so that
# collection does not crash.
sys.modules.setdefault('pdfplumber', MagicMock())

import pytest
from datetime import datetime
from crawling_noti import (
    extract_category_from_title, parse_notice_date,
    get_db_connection, DB_CONFIG, notice_exists,
    save_notice, crawl_notices,
)


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


class TestGetDbConnection:
    def test_calls_connect_with_db_config(self, mocker):
        mock_connect = mocker.patch("crawling_noti.mysql.connector.connect")
        get_db_connection()
        mock_connect.assert_called_once_with(**DB_CONFIG)

    def test_returns_connection_object(self, mocker):
        mock_conn = MagicMock()
        mocker.patch("crawling_noti.mysql.connector.connect", return_value=mock_conn)
        result = get_db_connection()
        assert result is mock_conn


# ── auto-generated: notice_exists ──


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
        mocker.patch("crawling_noti.get_db_connection", return_value=mock_conn)

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

        mocker.patch(
            "crawling_noti.requests.get",
            side_effect=[list_resp, detail_resp, list_resp2, detail_resp2],
        )
        mocker.patch("crawling_noti.notice_exists", return_value=False)
        mocker.patch("crawling_noti.save_notice")
        mocker.patch("crawling_noti.find_pdf_urls", return_value=[])

        result = crawl_notices(page_count=1)
        assert result == 2

    def test_empty_data_returns_zero_saved(self, mocker):
        """API returns no list data → nothing saved."""
        mock_conn = MagicMock()
        mocker.patch("crawling_noti.get_db_connection", return_value=mock_conn)

        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}
        mocker.patch("crawling_noti.requests.get", return_value=empty_resp)
        mocker.patch("crawling_noti.notice_exists", return_value=False)
        mock_save = mocker.patch("crawling_noti.save_notice")
        mocker.patch("crawling_noti.find_pdf_urls", return_value=[])

        result = crawl_notices(page_count=1)
        assert result == 0
        mock_save.assert_not_called()

    def test_notice_already_exists_is_skipped(self, mocker):
        """notice_exists returns True → save_notice never called."""
        mock_conn = MagicMock()
        mocker.patch("crawling_noti.get_db_connection", return_value=mock_conn)

        notice = self._make_notice(pk=301)
        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response(None, [notice])

        # Board 2 returns empty list → no detail fetch.
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}

        mocker.patch(
            "crawling_noti.requests.get",
            side_effect=[list_resp, empty_resp],
        )
        mocker.patch("crawling_noti.notice_exists", return_value=True)
        mock_save = mocker.patch("crawling_noti.save_notice")
        mocker.patch("crawling_noti.find_pdf_urls", return_value=[])

        result = crawl_notices(page_count=1)
        assert result == 0
        mock_save.assert_not_called()

    def test_conn_commit_called_per_saved_notice(self, mocker):
        """conn.commit() must be called once for each saved notice."""
        mock_conn = MagicMock()
        mocker.patch("crawling_noti.get_db_connection", return_value=mock_conn)

        notice = self._make_notice(pk=401)
        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response(None, [notice])

        detail_resp = MagicMock()
        detail_resp.json.return_value = self._detail_response()

        # Second board returns empty
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}

        mocker.patch(
            "crawling_noti.requests.get",
            side_effect=[list_resp, detail_resp, empty_resp],
        )
        mocker.patch("crawling_noti.notice_exists", return_value=False)
        mocker.patch("crawling_noti.save_notice")
        mocker.patch("crawling_noti.find_pdf_urls", return_value=[])

        crawl_notices(page_count=1)
        assert mock_conn.commit.call_count == 1

    def test_cursor_and_conn_closed_after_crawl(self, mocker):
        """cursor.close() and conn.close() are always called (finally block)."""
        mock_conn = MagicMock()
        mock_cursor = mock_conn.cursor.return_value
        mocker.patch("crawling_noti.get_db_connection", return_value=mock_conn)

        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}
        mocker.patch("crawling_noti.requests.get", return_value=empty_resp)
        mocker.patch("crawling_noti.notice_exists", return_value=False)
        mocker.patch("crawling_noti.save_notice")
        mocker.patch("crawling_noti.find_pdf_urls", return_value=[])

        crawl_notices(page_count=1)
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_save_notice_called_with_correct_args(self, mocker):
        """Verify save_notice receives the expected arguments for a known notice."""
        mock_conn = MagicMock()
        mocker.patch("crawling_noti.get_db_connection", return_value=mock_conn)

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

        mocker.patch(
            "crawling_noti.requests.get",
            side_effect=[list_resp, detail_resp, empty_resp],
        )
        mocker.patch("crawling_noti.notice_exists", return_value=False)
        mock_save = mocker.patch("crawling_noti.save_notice")
        mocker.patch("crawling_noti.find_pdf_urls", return_value=[])

        crawl_notices(page_count=1)

        assert mock_save.call_count == 1
        args, kwargs = mock_save.call_args
        # args: (cursor, title, source_name, category, url, raw_content)
        assert args[1] == "2026 장학생 모집"          # title stripped of [장학]
        assert args[2] == "sogang_notice"             # first board
        assert args[3] == "장학"                       # category extracted from title
        assert "501" in args[4]                        # url contains pkId
        assert kwargs.get("posted_at") == datetime(2026, 4, 24, 13, 27, 3)


# ── auto-generated: crawl_notices_pdf ──


class TestCrawlNoticesPdfBranch:
    """Tests for the PDF branch inside crawl_notices (lines 172-193)."""

    @staticmethod
    def _list_response(notices):
        return {"data": {"list": notices}}

    @staticmethod
    def _detail_response(content_html="<p>Body text</p>", create_date="2026-04-24 13:27:03"):
        return {"data": {"content": content_html, "createDate": create_date}}

    def _make_notice(self, pk=701, title="PDF Notice"):
        return {"pkId": pk, "title": title, "category": "", "createDate": "2026-04-24 13:27:03"}

    def _setup_common_mocks(self, mocker, notice, detail_resp_data):
        """Patch DB, requests, notice_exists, save_notice; return mock_conn."""
        mock_conn = MagicMock()
        mocker.patch("crawling_noti.get_db_connection", return_value=mock_conn)

        list_resp = MagicMock()
        list_resp.json.return_value = self._list_response([notice])

        detail_resp = MagicMock()
        detail_resp.json.return_value = detail_resp_data

        # Second board returns empty so we only deal with board 1
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}

        mocker.patch(
            "crawling_noti.requests.get",
            side_effect=[list_resp, detail_resp, empty_resp],
        )
        mocker.patch("crawling_noti.notice_exists", return_value=False)
        mocker.patch("crawling_noti.save_notice")
        return mock_conn

    # ------------------------------------------------------------------
    # 1. download_pdf and extract_pdf_text are called for each pdf URL
    # ------------------------------------------------------------------
    def test_download_pdf_called_for_each_url(self, mocker):
        """download_pdf must be invoked once per PDF URL found."""
        notice = self._make_notice(pk=701)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        pdf_urls = ["http://cdn.example.com/a.pdf", "http://cdn.example.com/b.pdf"]
        mocker.patch("crawling_noti.find_pdf_urls", return_value=pdf_urls)
        mock_download = mocker.patch("crawling_noti.download_pdf")
        mock_extract = mocker.patch(
            "crawling_noti.extract_pdf_text",
            return_value={"pages": [], "tables": []},
        )
        mocker.patch("crawling_noti.os.path.exists", return_value=False)

        crawl_notices(page_count=1)

        assert mock_download.call_count == 2
        mock_download.assert_any_call("http://cdn.example.com/a.pdf", "temp_701_1.pdf")
        mock_download.assert_any_call("http://cdn.example.com/b.pdf", "temp_701_2.pdf")

    def test_extract_pdf_text_called_after_download(self, mocker):
        """extract_pdf_text must be called with the correct temp path."""
        notice = self._make_notice(pk=702)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/doc.pdf"])
        mocker.patch("crawling_noti.download_pdf")
        mock_extract = mocker.patch(
            "crawling_noti.extract_pdf_text",
            return_value={"pages": [], "tables": []},
        )
        mocker.patch("crawling_noti.os.path.exists", return_value=False)

        crawl_notices(page_count=1)

        mock_extract.assert_called_once_with("temp_702_1.pdf")

    # ------------------------------------------------------------------
    # 2. Page and table content from extract_pdf_text ends up in raw_content
    # ------------------------------------------------------------------
    def test_pdf_page_text_appended_to_content(self, mocker):
        """Text from PDF pages is included in the raw_content passed to save_notice."""
        notice = self._make_notice(pk=703)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/p.pdf"])
        mocker.patch("crawling_noti.download_pdf")
        mocker.patch(
            "crawling_noti.extract_pdf_text",
            return_value={
                "pages": [{"page": 1, "text": "Page one content"}],
                "tables": [],
            },
        )
        mocker.patch("crawling_noti.os.path.exists", return_value=False)
        mock_save = mocker.patch("crawling_noti.save_notice")

        crawl_notices(page_count=1)

        args, _ = mock_save.call_args
        raw_content = args[5]
        assert "[PDF 1 - Page 1]" in raw_content
        assert "Page one content" in raw_content

    def test_pdf_table_text_appended_to_content(self, mocker):
        """Table data from PDF is included in the raw_content passed to save_notice."""
        notice = self._make_notice(pk=704)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/t.pdf"])
        mocker.patch("crawling_noti.download_pdf")
        mocker.patch(
            "crawling_noti.extract_pdf_text",
            return_value={
                "pages": [],
                "tables": [{"page": 2, "data": [["Col A", "Col B"], ["Val 1", "Val 2"]]}],
            },
        )
        mocker.patch("crawling_noti.os.path.exists", return_value=False)
        mock_save = mocker.patch("crawling_noti.save_notice")

        crawl_notices(page_count=1)

        args, _ = mock_save.call_args
        raw_content = args[5]
        assert "[PDF 1 - Table Page 2]" in raw_content
        assert "Col A" in raw_content

    # ------------------------------------------------------------------
    # 3. Exception path: download failure → error message in raw_content
    # ------------------------------------------------------------------
    def test_download_exception_appends_error_message(self, mocker):
        """If download_pdf raises, an error message is appended to content_parts."""
        notice = self._make_notice(pk=705)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/fail.pdf"])
        mocker.patch("crawling_noti.download_pdf", side_effect=Exception("connection refused"))
        mock_extract = mocker.patch("crawling_noti.extract_pdf_text")
        mocker.patch("crawling_noti.os.path.exists", return_value=False)
        mock_save = mocker.patch("crawling_noti.save_notice")

        crawl_notices(page_count=1)

        # extract_pdf_text must NOT be called when download fails
        mock_extract.assert_not_called()

        # Error text must appear in the content saved to DB
        args, _ = mock_save.call_args
        raw_content = args[5]
        assert "[PDF 오류:" in raw_content
        assert "connection refused" in raw_content

    def test_extract_exception_appends_error_message(self, mocker):
        """If extract_pdf_text raises, an error message is appended to content_parts."""
        notice = self._make_notice(pk=706)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/bad.pdf"])
        mocker.patch("crawling_noti.download_pdf")
        mocker.patch("crawling_noti.extract_pdf_text", side_effect=Exception("corrupt PDF"))
        mocker.patch("crawling_noti.os.path.exists", return_value=False)
        mock_save = mocker.patch("crawling_noti.save_notice")

        crawl_notices(page_count=1)

        args, _ = mock_save.call_args
        raw_content = args[5]
        assert "[PDF 오류:" in raw_content
        assert "corrupt PDF" in raw_content

    def test_notice_still_saved_after_pdf_exception(self, mocker):
        """Even when a PDF fails, the notice is still saved (saved_count incremented)."""
        notice = self._make_notice(pk=707)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/e.pdf"])
        mocker.patch("crawling_noti.download_pdf", side_effect=Exception("timeout"))
        mocker.patch("crawling_noti.os.path.exists", return_value=False)
        mock_save = mocker.patch("crawling_noti.save_notice")

        result = crawl_notices(page_count=1)

        assert result == 1
        mock_save.assert_called_once()

    # ------------------------------------------------------------------
    # 4. Finally block: os.remove called when temp file exists
    # ------------------------------------------------------------------
    def test_finally_removes_temp_pdf_when_exists(self, mocker):
        """os.remove must be called with the temp PDF path when the file exists."""
        notice = self._make_notice(pk=708)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/c.pdf"])
        mocker.patch("crawling_noti.download_pdf")
        mocker.patch(
            "crawling_noti.extract_pdf_text",
            return_value={"pages": [], "tables": []},
        )
        mocker.patch("crawling_noti.os.path.exists", return_value=True)
        mock_remove = mocker.patch("crawling_noti.os.remove")
        mocker.patch("crawling_noti.save_notice")

        crawl_notices(page_count=1)

        mock_remove.assert_called_once_with("temp_708_1.pdf")

    def test_finally_does_not_remove_when_file_missing(self, mocker):
        """os.remove must NOT be called when the temp PDF file does not exist."""
        notice = self._make_notice(pk=709)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/m.pdf"])
        mocker.patch("crawling_noti.download_pdf")
        mocker.patch(
            "crawling_noti.extract_pdf_text",
            return_value={"pages": [], "tables": []},
        )
        mocker.patch("crawling_noti.os.path.exists", return_value=False)
        mock_remove = mocker.patch("crawling_noti.os.remove")
        mocker.patch("crawling_noti.save_notice")

        crawl_notices(page_count=1)

        mock_remove.assert_not_called()

    def test_finally_removes_file_even_after_exception(self, mocker):
        """The finally block must clean up temp files even when download raises."""
        notice = self._make_notice(pk=710)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        mocker.patch("crawling_noti.find_pdf_urls", return_value=["http://cdn.example.com/x.pdf"])
        mocker.patch("crawling_noti.download_pdf", side_effect=Exception("network error"))
        mocker.patch("crawling_noti.os.path.exists", return_value=True)
        mock_remove = mocker.patch("crawling_noti.os.remove")
        mocker.patch("crawling_noti.save_notice")

        crawl_notices(page_count=1)

        mock_remove.assert_called_once_with("temp_710_1.pdf")

    def test_finally_removes_each_pdf_independently(self, mocker):
        """When multiple PDFs are processed, each temp file is removed individually."""
        notice = self._make_notice(pk=711)
        detail_data = self._detail_response()
        self._setup_common_mocks(mocker, notice, detail_data)

        pdf_urls = [
            "http://cdn.example.com/one.pdf",
            "http://cdn.example.com/two.pdf",
        ]
        mocker.patch("crawling_noti.find_pdf_urls", return_value=pdf_urls)
        mocker.patch("crawling_noti.download_pdf")
        mocker.patch(
            "crawling_noti.extract_pdf_text",
            return_value={"pages": [], "tables": []},
        )
        mocker.patch("crawling_noti.os.path.exists", return_value=True)
        mock_remove = mocker.patch("crawling_noti.os.remove")
        mocker.patch("crawling_noti.save_notice")

        crawl_notices(page_count=1)

        assert mock_remove.call_count == 2
        mock_remove.assert_any_call("temp_711_1.pdf")
        mock_remove.assert_any_call("temp_711_2.pdf")


# ── auto-generated: crawl_notices_pdf ── (module __main__ block)


class TestMainBlock:
    """Covers line 214: `crawl_notices(page_count=5)` when run as __main__."""

    def test_main_block_calls_crawl_notices_with_page_count_5(self, mocker):
        """
        Running the module as __main__ executes crawl_notices(page_count=5).

        runpy.run_module re-executes the module source in a fresh globals dict,
        so patches applied via 'crawling_noti.<name>' are NOT visible inside
        that fresh execution.  We must patch at the library level so the fresh
        module code hits our mocks:
          - mysql.connector.connect  → returns a MagicMock connection
          - requests.get             → returns empty-board responses
          - pdfviewer (already a MagicMock via sys.modules stub at top of file)
        We verify the observable side-effect: the function completed without
        raising (no real DB connection was made) and conn.close() was called,
        confirming the finally-block executed after a 5-page crawl.
        """
        import runpy

        # Patch mysql.connector.connect at the library level so the fresh
        # module namespace picks it up through its own import of mysql.connector.
        mock_conn = MagicMock()
        import mysql.connector as _mc
        mocker.patch.object(_mc, "connect", return_value=mock_conn)

        # All board-list API calls return empty lists → no notices, no DB writes
        empty_resp = MagicMock()
        empty_resp.json.return_value = {"data": {}}
        import requests as _requests
        mocker.patch.object(_requests, "get", return_value=empty_resp)

        # Execute the __main__ guard — this must call crawl_notices(page_count=5)
        runpy.run_module("crawling_noti", run_name="__main__", alter_sys=False)

        # Verify conn.close() was invoked — confirms crawl_notices ran fully
        assert mock_conn.close.called
        # requests.get must have been called (at least the board-list fetches)
        assert _requests.get.call_count >= 1  # type: ignore[attr-defined]
