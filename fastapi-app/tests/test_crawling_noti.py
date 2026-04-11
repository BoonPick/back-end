"""
crawling_noti.py 테스트
"""

import pytest
from unittest.mock import MagicMock, patch, call

from crawling_noti import (
    notice_exists,
    extract_category_from_title,
    save_notice,
    crawl_notices,
)


# ── notice_exists ─────────────────────────────────────────────────

class TestNoticeExists:
    def test_returns_true_when_url_exists(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)

        result = notice_exists(mock_cursor, "https://example.com/notice?pkId=1")

        assert result is True
        mock_cursor.execute.assert_called_once()

    def test_returns_false_when_url_not_found(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        result = notice_exists(mock_cursor, "https://example.com/notice?pkId=99")

        assert result is False

    def test_passes_url_as_parameter(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        url = "https://www.sogang.ac.kr/ko/notice?pkId=42"

        notice_exists(mock_cursor, url)

        args = mock_cursor.execute.call_args[0]
        assert url in args[1]


# ── extract_category_from_title ────────────────────────────────────

class TestExtractCategoryFromTitle:
    def test_extracts_bracket_category(self):
        category, title = extract_category_from_title("[장학] 2025년 장학생 모집")
        assert category == "장학"
        assert title == "2025년 장학생 모집"

    def test_no_bracket_returns_empty_category(self):
        category, title = extract_category_from_title("일반 공지사항입니다")
        assert category == ""
        assert title == "일반 공지사항입니다"

    def test_strips_whitespace(self):
        category, title = extract_category_from_title("[ 학사 ]  수강신청 안내")
        assert category == "학사"
        assert title == "수강신청 안내"

    def test_empty_string(self):
        category, title = extract_category_from_title("")
        assert category == ""
        assert title == ""

    def test_only_brackets(self):
        category, title = extract_category_from_title("[공지]")
        assert category == "공지"
        assert title == ""

    def test_multiple_brackets_only_first_extracted(self):
        category, title = extract_category_from_title("[학사] [긴급] 수강신청 변경")
        assert category == "학사"
        assert title == "[긴급] 수강신청 변경"


# ── save_notice ───────────────────────────────────────────────────

class TestSaveNotice:
    def test_executes_insert_with_correct_args(self):
        mock_cursor = MagicMock()

        save_notice(
            cursor=mock_cursor,
            title="테스트 공지",
            source_name="sogang_notice",
            category="장학",
            url="https://www.sogang.ac.kr/ko/notice?pkId=1",
            raw_content="공지 내용",
        )

        mock_cursor.execute.assert_called_once()
        sql, params = mock_cursor.execute.call_args[0]
        assert "INSERT INTO contents" in sql
        assert "테스트 공지" in params
        assert "sogang_notice" in params
        assert "장학" in params

    def test_all_fields_passed_to_insert(self):
        mock_cursor = MagicMock()
        url = "https://www.sogang.ac.kr/ko/notice?pkId=5"

        save_notice(mock_cursor, "제목", "source", "카테고리", url, "내용")

        _, params = mock_cursor.execute.call_args[0]
        assert url in params
        assert "내용" in params


# ── crawl_notices ─────────────────────────────────────────────────

def make_list_response(notices):
    mock = MagicMock()
    mock.json.return_value = {"data": {"list": notices}}
    return mock


def make_detail_response(content="<p>공지 내용입니다</p>"):
    mock = MagicMock()
    mock.json.return_value = {"data": {"content": content}}
    return mock


def make_mock_db(fetchone_return=None):
    """fetchone_return=None → notice 미존재 (저장 대상)"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_return
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


def mock_requests_get_factory(notices):
    """boardList URL → list 응답, 그 외 → detail 응답"""
    def mock_get(url, *args, **kwargs):
        if "boardList" in url:
            return make_list_response(notices)
        return make_detail_response()
    return mock_get


class TestCrawlNotices:
    NOTICE = {"pkId": 42, "title": "[장학] 테스트 공지", "category": ""}

    def test_saves_new_notices(self):
        mock_conn, mock_cursor = make_mock_db(fetchone_return=None)

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_requests_get_factory([self.NOTICE])), \
             patch("crawling_noti.find_pdf_urls", return_value=[]):
            result = crawl_notices(page_count=1)

        # BOARDS에 게시판이 2개이므로 각각 1건씩 저장
        assert result == 2
        assert mock_conn.commit.call_count == 2

    def test_skips_existing_notices(self):
        # fetchone이 값을 반환 → 이미 존재
        mock_conn, mock_cursor = make_mock_db(fetchone_return=(1,))

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_requests_get_factory([self.NOTICE])), \
             patch("crawling_noti.find_pdf_urls", return_value=[]):
            result = crawl_notices(page_count=1)

        assert result == 0
        mock_conn.commit.assert_not_called()

    def test_empty_board_response_saves_nothing(self):
        mock_conn, _ = make_mock_db()

        def mock_get(url, *args, **kwargs):
            r = MagicMock()
            r.json.return_value = {"data": {"list": []}}
            return r

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_get):
            result = crawl_notices(page_count=1)

        assert result == 0

    def test_connection_always_closed(self):
        mock_conn, _ = make_mock_db()

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_requests_get_factory([])):
            crawl_notices(page_count=1)

        mock_conn.close.assert_called_once()
        mock_conn.cursor().close.assert_called()

    def test_notice_title_category_parsed(self):
        mock_conn, mock_cursor = make_mock_db(fetchone_return=None)
        notice = {"pkId": 10, "title": "[학사] 수강신청 안내", "category": ""}

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_requests_get_factory([notice])), \
             patch("crawling_noti.find_pdf_urls", return_value=[]):
            crawl_notices(page_count=1)

        # execute 호출 중 INSERT 호출의 파라미터 확인
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT" in str(c)
        ]
        assert len(insert_calls) > 0
        params = insert_calls[0][0][1]
        assert "수강신청 안내" in params   # 괄호 제거된 제목
        assert "학사" in params           # 추출된 카테고리

    def test_pdf_content_appended_to_raw_content(self):
        mock_conn, mock_cursor = make_mock_db(fetchone_return=None)
        notice = {"pkId": 7, "title": "PDF 첨부 공지", "category": ""}
        pdf_url = "https://example.com/file.pdf"

        mock_extract_result = {
            "pages": [{"page": 1, "text": "PDF 페이지 내용"}],
            "tables": [],
        }

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_requests_get_factory([notice])), \
             patch("crawling_noti.find_pdf_urls", return_value=[pdf_url]), \
             patch("crawling_noti.download_pdf"), \
             patch("crawling_noti.extract_pdf_text", return_value=mock_extract_result), \
             patch("os.path.exists", return_value=False):
            crawl_notices(page_count=1)

        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT" in str(c)
        ]
        raw_content = insert_calls[0][0][1][4]  # raw_content는 5번째 파라미터
        assert "PDF 페이지 내용" in raw_content


# ── auto-generated: crawl_notices ──────────────────────────────────

class TestCrawlNoticesMultiplePages:
    """page_count > 1 일 때 모든 페이지를 순회하는지 확인."""

    def test_iterates_all_pages(self):
        mock_conn, mock_cursor = make_mock_db(fetchone_return=None)
        notice_p1 = {"pkId": 100, "title": "페이지1 공지", "category": ""}
        notice_p2 = {"pkId": 200, "title": "페이지2 공지", "category": ""}

        call_count = {"n": 0}

        def mock_get(url, *args, **kwargs):
            resp = MagicMock()
            if "boardList" in url:
                call_count["n"] += 1
                if "pageNum=1" in url:
                    resp.json.return_value = {"data": {"list": [notice_p1]}}
                elif "pageNum=2" in url:
                    resp.json.return_value = {"data": {"list": [notice_p2]}}
                else:
                    resp.json.return_value = {"data": {"list": []}}
            else:
                resp.json.return_value = {"data": {"content": "<p>내용</p>"}}
            return resp

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_get), \
             patch("crawling_noti.find_pdf_urls", return_value=[]), \
             patch("crawling_noti.BOARDS", [{"source_name": "테스트", "bbs_config_fk": "1",
                                              "page_url": "http://test", "page_size": 10}]):
            result = crawl_notices(page_count=2)

        # 두 페이지 모두에서 boardList 호출
        assert call_count["n"] >= 2
        assert result == 2


class TestCrawlNoticesMultipleBoards:
    """BOARDS 리스트에 여러 게시판이 있을 때 모두 크롤링."""

    def test_saves_from_each_board(self):
        mock_conn, mock_cursor = make_mock_db(fetchone_return=None)

        boards = [
            {"source_name": "게시판A", "bbs_config_fk": "10",
             "page_url": "http://a", "page_size": 5},
            {"source_name": "게시판B", "bbs_config_fk": "20",
             "page_url": "http://b", "page_size": 5},
        ]

        notice_a = {"pkId": 1, "title": "A 공지", "category": ""}
        notice_b = {"pkId": 2, "title": "B 공지", "category": ""}

        def mock_get(url, *args, **kwargs):
            resp = MagicMock()
            if "boardList" in url:
                if "bbsConfigFk=10" in url:
                    resp.json.return_value = {"data": {"list": [notice_a]}}
                elif "bbsConfigFk=20" in url:
                    resp.json.return_value = {"data": {"list": [notice_b]}}
                else:
                    resp.json.return_value = {"data": {"list": []}}
            else:
                resp.json.return_value = {"data": {"content": "<p>내용</p>"}}
            return resp

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_get), \
             patch("crawling_noti.find_pdf_urls", return_value=[]), \
             patch("crawling_noti.BOARDS", boards):
            result = crawl_notices(page_count=1)

        assert result == 2
        assert mock_conn.commit.call_count == 2


class TestCrawlNoticesNullDataResponse:
    """응답의 data 키 자체가 None 인 경우 안전하게 건너뜀."""

    def test_data_is_none(self):
        mock_conn, _ = make_mock_db()

        def mock_get(url, *args, **kwargs):
            resp = MagicMock()
            resp.json.return_value = {"data": None}
            return resp

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_get):
            result = crawl_notices(page_count=1)

        assert result == 0

    def test_top_level_data_key_missing(self):
        mock_conn, _ = make_mock_db()

        def mock_get(url, *args, **kwargs):
            resp = MagicMock()
            resp.json.return_value = {}
            return resp

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get", side_effect=mock_get):
            result = crawl_notices(page_count=1)

        assert result == 0


class TestCrawlNoticesPdfErrorHandling:
    """PDF 다운로드/추출 중 예외 발생 시에도 저장은 진행."""

    def test_pdf_download_failure_still_saves(self):
        mock_conn, mock_cursor = make_mock_db(fetchone_return=None)
        notice = {"pkId": 50, "title": "PDF 오류 테스트", "category": "일반"}

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get",
                   side_effect=mock_requests_get_factory([notice])), \
             patch("crawling_noti.find_pdf_urls",
                   return_value=["https://example.com/broken.pdf"]), \
             patch("crawling_noti.download_pdf",
                   side_effect=Exception("네트워크 오류")), \
             patch("os.path.exists", return_value=False):
            result = crawl_notices(page_count=1)

        assert result >= 1
        # raw_content에 오류 메시지 포함 확인
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list if "INSERT" in str(c)
        ]
        raw_content = insert_calls[0][0][1][4]
        assert "PDF 오류" in raw_content
        assert "네트워크 오류" in raw_content

    def test_pdf_extract_failure_still_saves(self):
        mock_conn, mock_cursor = make_mock_db(fetchone_return=None)
        notice = {"pkId": 51, "title": "PDF 추출 오류 테스트", "category": "일반"}

        with patch("crawling_noti.get_db_connection", return_value=mock_conn), \
             patch("crawling_noti.requests.get",
                   side_effect=mock_requests_get_factory([notice])), \
             patch("crawling_noti.find_pdf_urls",
                   return_value=["https://example.com/extract_fail.pdf"]), \
             patch("crawling_noti.download_pdf"), \
             patch("crawling_noti.extract_pdf_text",
                   side_effect=Exception("추출 오류")), \
             patch("os.path.exists", return_value=False):
            result = crawl_notices(page_count=1)

        assert result >= 1
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list if "INSERT" in str(c)
        ]
        raw_content = insert_calls[0][0][1][4]
        assert "PDF 오류" in raw_content
        assert "추출 오류" in raw_content
