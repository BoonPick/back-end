"""
crawling_noti.py 테스트
"""

import pytest
import mysql.connector
from unittest.mock import MagicMock, patch, call

from crawling_noti import (
    notice_exists,
    extract_category_from_title,
    save_notice,
    crawl_notices,
    parse_notice_date,
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
             patch("crawling_noti.parse_notice_date", return_value=None), \
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
             patch("crawling_noti.parse_notice_date", return_value=None), \
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
             patch("crawling_noti.parse_notice_date", return_value=None), \
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
             patch("crawling_noti.parse_notice_date", return_value=None), \
             patch("os.path.exists", return_value=False):
            result = crawl_notices(page_count=1)

        assert result >= 1
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list if "INSERT" in str(c)
        ]
        raw_content = insert_calls[0][0][1][4]
        assert "PDF 오류" in raw_content
        assert "추출 오류" in raw_content


# ── auto-generated: parse_notice_date ──────────────────────────────────
class TestParseNoticeDate:
    """parse_notice_date 함수에 대한 테스트."""

    # ── 정상 케이스 ──

    def test_createDate_datetime_format(self):
        notice = {"createDate": "2024-01-15 10:30:00"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0

    def test_registDate_datetime_format(self):
        notice = {"registDate": "2023-12-25 08:00:00"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25

    def test_regDate_field(self):
        notice = {"regDate": "2024-06-01 12:00:00"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.month == 6

    def test_writeDate_field(self):
        notice = {"writeDate": "2024-03-10 09:15:30"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.day == 10
        assert result.hour == 9

    def test_modifyDate_field(self):
        notice = {"modifyDate": "2024-07-20 14:00:00"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.month == 7

    def test_updDate_field(self):
        notice = {"updDate": "2024-11-30 23:59:59"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59

    def test_iso_format_with_T_separator(self):
        notice = {"createDate": "2024-05-20T16:45:30"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2024
        assert result.month == 5
        assert result.day == 20
        assert result.hour == 16
        assert result.minute == 45

    def test_date_only_format(self):
        notice = {"createDate": "2024-08-15"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2024
        assert result.month == 8
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0

    def test_compact_date_format_yyyymmdd(self):
        notice = {"createDate": "20240315"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    # ── 필드 우선순위 테스트 ──

    def test_createDate_has_highest_priority(self):
        notice = {
            "createDate": "2024-01-01 00:00:00",
            "registDate": "2023-06-15 00:00:00",
            "regDate": "2022-12-31 00:00:00",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_registDate_used_when_createDate_missing(self):
        notice = {
            "registDate": "2023-06-15 00:00:00",
            "regDate": "2022-12-31 00:00:00",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2023
        assert result.month == 6

    def test_regDate_used_when_earlier_fields_missing(self):
        notice = {
            "regDate": "2022-12-31 00:00:00",
            "writeDate": "2021-01-01 00:00:00",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2022

    def test_writeDate_used_when_earlier_fields_missing(self):
        notice = {
            "writeDate": "2021-04-10 00:00:00",
            "modifyDate": "2020-01-01 00:00:00",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2021
        assert result.month == 4

    def test_modifyDate_used_when_earlier_fields_missing(self):
        notice = {
            "modifyDate": "2020-09-05 11:22:33",
            "updDate": "2019-01-01 00:00:00",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2020
        assert result.month == 9

    def test_updDate_used_as_last_resort(self):
        notice = {"updDate": "2019-02-28 07:30:00"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2019
        assert result.month == 2

    def test_skips_empty_string_field_to_next(self):
        notice = {
            "createDate": "",
            "registDate": "2023-11-11 11:11:11",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2023
        assert result.month == 11

    def test_skips_none_field_to_next(self):
        notice = {
            "createDate": None,
            "registDate": None,
            "regDate": "2022-05-05 05:05:05",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2022
        assert result.month == 5

    # ── 엣지 케이스 ──

    def test_empty_dict_returns_none(self):
        result = parse_notice_date({})
        assert result is None

    def test_no_recognized_fields_returns_none(self):
        notice = {"title": "공지사항", "content": "내용", "author": "관리자"}
        result = parse_notice_date(notice)
        assert result is None

    def test_all_candidate_fields_empty_returns_none(self):
        notice = {
            "createDate": "",
            "registDate": "",
            "regDate": "",
            "writeDate": "",
            "modifyDate": "",
            "updDate": "",
        }
        result = parse_notice_date(notice)
        assert result is None

    def test_all_candidate_fields_none_returns_none(self):
        notice = {
            "createDate": None,
            "registDate": None,
            "regDate": None,
            "writeDate": None,
            "modifyDate": None,
            "updDate": None,
        }
        result = parse_notice_date(notice)
        assert result is None

    def test_string_longer_than_19_chars_truncated(self):
        # 밀리초가 포함된 긴 문자열도 19자 잘림으로 파싱 가능
        notice = {"createDate": "2024-01-15 10:30:00.123456"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2024
        assert result.second == 0

    def test_iso_format_with_timezone_suffix_truncated(self):
        notice = {"createDate": "2024-05-20T16:45:30+09:00"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.hour == 16
        assert result.minute == 45

    def test_numeric_value_converted_to_string(self):
        # 정수 값이 들어와도 str() 변환으로 처리
        notice = {"createDate": 20240315}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_integer_registDate(self):
        notice = {"registDate": 20231225}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.month == 12
        assert result.day == 25

    # ── 예외/잘못된 형식 케이스 ──

    def test_invalid_date_format_returns_none(self):
        notice = {"createDate": "15/01/2024"}
        result = parse_notice_date(notice)
        assert result is None

    def test_completely_invalid_string_returns_none(self):
        notice = {"createDate": "not-a-date"}
        result = parse_notice_date(notice)
        assert result is None

    def test_random_garbage_in_all_fields_returns_none(self):
        notice = {
            "createDate": "abc",
            "registDate": "xyz",
            "regDate": "!!!",
            "writeDate": "garbage",
            "modifyDate": "invalid",
            "updDate": "nope",
        }
        result = parse_notice_date(notice)
        assert result is None

    def test_partial_date_string_returns_none(self):
        notice = {"createDate": "2024-01"}
        result = parse_notice_date(notice)
        assert result is None

    def test_invalid_first_field_valid_second_field(self):
        notice = {
            "createDate": "not-a-date-at-all",
            "registDate": "2023-07-04 12:00:00",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2023
        assert result.month == 7
        assert result.day == 4

    def test_invalid_format_in_multiple_fields_then_valid(self):
        notice = {
            "createDate": "invalid",
            "registDate": "also-invalid",
            "regDate": "still-bad",
            "writeDate": "2021-12-25",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2021
        assert result.month == 12
        assert result.day == 25

    def test_zero_value_field_skipped(self):
        # 0은 falsy이므로 스킵됨
        notice = {
            "createDate": 0,
            "registDate": "2023-03-03 03:03:03",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2023
        assert result.month == 3

    def test_false_value_field_skipped(self):
        notice = {
            "createDate": False,
            "registDate": "2022-02-02 02:02:02",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2022

    def test_whitespace_only_field_attempted_and_fails(self):
        # "   " is truthy, so it will be attempted but fail all formats
        notice = {
            "createDate": "   ",
            "registDate": "2024-10-10 10:10:10",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 2024
        assert result.month == 10

    def test_boundary_date_min(self):
        notice = {"createDate": "0001-01-01 00:00:00"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.year == 1

    def test_boundary_date_leap_year(self):
        notice = {"createDate": "2024-02-29 00:00:00"}
        result = parse_notice_date(notice)
        assert result is not None
        assert result.month == 2
        assert result.day == 29

    def test_non_leap_year_feb_29_returns_none(self):
        # 2023-02-29 is invalid
        notice = {"createDate": "2023-02-29 00:00:00"}
        result = parse_notice_date(notice)
        assert result is None

    def test_return_type_is_datetime(self):
        from datetime import datetime as dt
        notice = {"createDate": "2024-06-15 12:00:00"}
        result = parse_notice_date(notice)
        assert isinstance(result, dt)

    def test_compact_format_with_extra_chars_fails_gracefully(self):
        # "2024031599" -> str[:19] = "2024031599", doesn't match any format
        # Actually "2024031599" is 10 chars, [:19] keeps it, and it won't match
        notice = {"createDate": "2024031599"}
        result = parse_notice_date(notice)
        assert result is None

    def test_empty_list_value_is_falsy_skipped(self):
        notice = {
            "createDate": [],
            "registDate": "2024-04-04 04:04:04",
        }
        result = parse_notice_date(notice)
        assert result is not None
        assert result.month == 4


# ── auto-generated: save_notice ──────────────────────────────────
class TestSaveNotice:
    """save_notice 함수 테스트"""

    def test_save_notice_with_posted_at(self):
        """posted_at이 제공된 경우 created_at에 posted_at 값이 사용되는지 확인"""
        cursor = MagicMock()
        save_notice(
            cursor,
            title="테스트 공지",
            source_name="학교",
            category="일반",
            url="https://example.com/1",
            raw_content="본문 내용입니다.",
            posted_at="2024-01-15 10:00:00",
        )
        cursor.execute.assert_called_once()
        args, kwargs = cursor.execute.call_args
        sql = args[0]
        params = args[1]
        assert "VALUES (%s, %s, %s, %s, %s, %s, NOW())" in sql
        assert params == (
            "테스트 공지", "학교", "일반",
            "https://example.com/1", "본문 내용입니다.",
            "2024-01-15 10:00:00",
        )

    def test_save_notice_without_posted_at(self):
        """posted_at이 None인 경우 created_at과 updated_at 모두 NOW() 사용"""
        cursor = MagicMock()
        save_notice(
            cursor,
            title="공지2",
            source_name="도서관",
            category="학사",
            url="https://example.com/2",
            raw_content="내용2",
            posted_at=None,
        )
        cursor.execute.assert_called_once()
        args, _ = cursor.execute.call_args
        sql = args[0]
        params = args[1]
        assert "VALUES (%s, %s, %s, %s, %s, NOW(), NOW())" in sql
        assert params == ("공지2", "도서관", "학사", "https://example.com/2", "내용2")

    def test_save_notice_default_posted_at_is_none(self):
        """posted_at 인자를 생략하면 기본값 None으로 NOW(), NOW() 분기 실행"""
        cursor = MagicMock()
        save_notice(cursor, "제목", "출처", "카테고리", "http://url", "내용")
        args, _ = cursor.execute.call_args
        sql = args[0]
        assert "NOW(), NOW()" in sql
        assert len(args[1]) == 5

    def test_save_notice_empty_strings(self):
        """빈 문자열 값들이 그대로 DB에 전달되는지 확인"""
        cursor = MagicMock()
        save_notice(cursor, "", "", "", "", "", posted_at=None)
        cursor.execute.assert_called_once()
        args, _ = cursor.execute.call_args
        assert args[1] == ("", "", "", "", "")

    def test_save_notice_with_empty_string_posted_at(self):
        """posted_at이 빈 문자열(falsy but not None)이면 posted_at 분기 실행"""
        cursor = MagicMock()
        save_notice(cursor, "제목", "출처", "카테고리", "http://url", "내용", posted_at="")
        args, _ = cursor.execute.call_args
        sql = args[0]
        # 빈 문자열은 not None이므로 posted_at 분기
        assert "VALUES (%s, %s, %s, %s, %s, %s, NOW())" in sql
        assert args[1][-1] == ""

    def test_save_notice_long_raw_content(self):
        """매우 긴 raw_content가 올바르게 전달되는지 확인"""
        cursor = MagicMock()
        long_content = "A" * 100000
        save_notice(cursor, "제목", "출처", "카테고리", "http://url", long_content)
        args, _ = cursor.execute.call_args
        assert args[1][4] == long_content

    def test_save_notice_special_characters_in_title(self):
        """특수 문자가 포함된 제목이 올바르게 전달되는지 확인"""
        cursor = MagicMock()
        special_title = "공지: [긴급] 'SQL' \"injection\" -- DROP TABLE; 테스트 & <html>"
        save_notice(cursor, special_title, "출처", "카테고리", "http://url", "내용")
        args, _ = cursor.execute.call_args
        assert args[1][0] == special_title

    def test_save_notice_unicode_content(self):
        """유니코드(이모지 등) 내용이 올바르게 전달되는지 확인"""
        cursor = MagicMock()
        unicode_content = "공지사항 🎓📚 일본어: テスト 中文: 测试"
        save_notice(cursor, "유니코드", "출처", "카테고리", "http://url", unicode_content)
        args, _ = cursor.execute.call_args
        assert args[1][4] == unicode_content

    def test_save_notice_posted_at_datetime_object(self):
        """posted_at에 datetime 객체가 전달되어도 정상 동작"""
        from datetime import datetime as dt
        cursor = MagicMock()
        posted = dt(2024, 6, 15, 12, 30, 0)
        save_notice(cursor, "제목", "출처", "카테고리", "http://url", "내용", posted_at=posted)
        args, _ = cursor.execute.call_args
        assert args[1][-1] == posted
        assert len(args[1]) == 6

    def test_save_notice_cursor_execute_raises_exception(self):
        """cursor.execute가 예외를 발생시키면 그대로 전파"""
        cursor = MagicMock()
        cursor.execute.side_effect = Exception("DB connection lost")
        with pytest.raises(Exception, match="DB connection lost"):
            save_notice(cursor, "제목", "출처", "카테고리", "http://url", "내용")

    def test_save_notice_cursor_execute_called_exactly_once_with_posted_at(self):
        """posted_at이 있을 때 execute가 정확히 1회 호출"""
        cursor = MagicMock()
        save_notice(cursor, "t", "s", "c", "u", "r", posted_at="2024-01-01")
        assert cursor.execute.call_count == 1

    def test_save_notice_cursor_execute_called_exactly_once_without_posted_at(self):
        """posted_at이 None일 때 execute가 정확히 1회 호출"""
        cursor = MagicMock()
        save_notice(cursor, "t", "s", "c", "u", "r")
        assert cursor.execute.call_count == 1

    def test_save_notice_none_values_for_optional_fields(self):
        """title 등 필드에 None을 넣어도 그대로 전달"""
        cursor = MagicMock()
        save_notice(cursor, None, None, None, None, None, posted_at=None)
        args, _ = cursor.execute.call_args
        assert args[1] == (None, None, None, None, None)

    def test_save_notice_posted_at_zero_is_not_none(self):
        """posted_at=0은 None이 아니므로 posted_at 분기로 진입"""
        cursor = MagicMock()
        save_notice(cursor, "제목", "출처", "카테고리", "http://url", "내용", posted_at=0)
        args, _ = cursor.execute.call_args
        sql = args[0]
        assert "VALUES (%s, %s, %s, %s, %s, %s, NOW())" in sql
        assert args[1][-1] == 0

    def test_save_notice_posted_at_false_is_not_none(self):
        """posted_at=False는 None이 아니므로 posted_at 분기로 진입"""
        cursor = MagicMock()
        save_notice(cursor, "제목", "출처", "카테고리", "http://url", "내용", posted_at=False)
        args, _ = cursor.execute.call_args
        assert len(args[1]) == 6
        assert args[1][-1] is False

    def test_save_notice_sql_contains_insert_into_contents(self):
        """실행되는 SQL이 INSERT INTO contents를 포함하는지 확인"""
        cursor = MagicMock()
        save_notice(cursor, "t", "s", "c", "u", "r")
        args, _ = cursor.execute.call_args
        assert "INSERT INTO contents" in args[0]

    def test_save_notice_sql_columns_correct(self):
        """SQL에 올바른 컬럼명이 포함되어 있는지 확인"""
        cursor = MagicMock()
        save_notice(cursor, "t", "s", "c", "u", "r", posted_at="2024-01-01")
        args, _ = cursor.execute.call_args
        sql = args[0]
        for col in ["title", "source_name", "category", "url", "raw_content", "created_at", "updated_at"]:
            assert col in sql

    def test_save_notice_multiline_raw_content(self):
        """여러 줄의 raw_content(본문 + PDF 텍스트)가 올바르게 전달"""
        cursor = MagicMock()
        content = "본문 내용\n\n--- PDF 텍스트 ---\nPDF에서 추출된 내용\n페이지 2 내용"
        save_notice(cursor, "제목", "출처", "카테고리", "http://url", content)
        args, _ = cursor.execute.call_args
        assert args[1][4] == content

    def test_save_notice_returns_none(self):
        """save_notice 함수의 반환값이 None인지 확인 (명시적 return 없음)"""
        cursor = MagicMock()
        result = save_notice(cursor, "t", "s", "c", "u", "r")
        assert result is None

    def test_save_notice_mysql_integrity_error_propagates(self):
        """mysql.connector.IntegrityError가 발생하면 그대로 전파"""
        cursor = MagicMock()
        cursor.execute.side_effect = mysql.connector.IntegrityError("Duplicate entry")
        with pytest.raises(mysql.connector.IntegrityError):
            save_notice(cursor, "제목", "출처", "카테고리", "http://dup", "내용")

    def test_save_notice_params_order_with_posted_at(self):
        """posted_at이 있을 때 파라미터 순서가 정확한지 확인"""
        cursor = MagicMock()
        save_notice(cursor, "A", "B", "C", "D", "E", posted_at="F")
        args, _ = cursor.execute.call_args
        assert args[1] == ("A", "B", "C", "D", "E", "F")

    def test_save_notice_params_order_without_posted_at(self):
        """posted_at이 None일 때 파라미터 순서가 정확한지 확인"""
        cursor = MagicMock()
        save_notice(cursor, "A", "B", "C", "D", "E")
        args, _ = cursor.execute.call_args
        assert args[1] == ("A", "B", "C", "D", "E")
