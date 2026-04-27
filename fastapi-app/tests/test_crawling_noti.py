import pytest
from datetime import datetime
from crawling_noti import extract_category_from_title, parse_notice_date


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
