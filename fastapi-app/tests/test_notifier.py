"""Tests for notifier.py — per-user email notification dispatch."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import notifier


class TestSplit:
    def test_none_returns_empty(self):
        assert notifier._split(None) == []

    def test_empty_string_returns_empty(self):
        assert notifier._split("") == []

    def test_single_value(self):
        assert notifier._split("keyword") == ["keyword"]

    def test_multiple_values(self):
        assert notifier._split("a, b, c") == ["a", "b", "c"]

    def test_strips_whitespace(self):
        assert notifier._split("  x , y  ") == ["x", "y"]

    def test_ignores_empty_tokens(self):
        assert notifier._split(",,,") == []


class TestMatchScore:
    def test_no_keywords_returns_100(self):
        assert notifier._match_score("anything", "content", []) == 100

    def test_all_keywords_match(self):
        score = notifier._match_score("python django", "fastapi", ["python", "django"])
        assert score == 100

    def test_no_keywords_match(self):
        score = notifier._match_score("hello world", "test", ["python", "java"])
        assert score == 0

    def test_partial_match(self):
        score = notifier._match_score("python hello", "world", ["python", "java"])
        assert score == 50

    def test_case_insensitive(self):
        score = notifier._match_score("Python", "content", ["python"])
        assert score == 100

    def test_content_also_searched(self):
        score = notifier._match_score("title", "keyword_here", ["keyword_here"])
        assert score == 100


class TestSummary:
    def test_short_text_unchanged(self):
        assert notifier._summary("hello") == "hello"

    def test_long_text_truncated(self):
        long = "x" * 300
        result = notifier._summary(long)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_exactly_200_no_ellipsis(self):
        text = "a" * 200
        result = notifier._summary(text)
        assert result == text
        assert not result.endswith("...")

    def test_none_returns_empty(self):
        assert notifier._summary(None) == ""

    def test_newlines_replaced(self):
        result = notifier._summary("line1\nline2")
        assert "\n" not in result

    def test_custom_n(self):
        result = notifier._summary("abcdef", n=3)
        assert result == "abc..."


class TestIsActive:
    def _now(self):
        return datetime(2024, 6, 1, 12, 0, 0)

    def test_job_always_open(self):
        assert notifier._is_active("job", None, True, None, self._now()) is True

    def test_job_no_deadline_active(self):
        assert notifier._is_active("job", None, False, None, self._now()) is True

    def test_job_future_deadline_active(self):
        future = (self._now() + timedelta(days=10)).date()
        assert notifier._is_active("job", future, False, None, self._now()) is True

    def test_job_past_deadline_inactive(self):
        from datetime import date
        past = date(2020, 1, 1)
        assert notifier._is_active("job", past, False, None, self._now()) is False

    def test_announcement_within_6months(self):
        created = self._now() - timedelta(days=90)
        assert notifier._is_active("announcement", None, None, created, self._now()) is True

    def test_announcement_over_6months(self):
        created = self._now() - timedelta(days=200)
        assert notifier._is_active("announcement", None, None, created, self._now()) is False

    def test_no_created_at_returns_true(self):
        assert notifier._is_active("scholarship", None, None, None, self._now()) is True


class TestJobPassesFilters:
    def test_no_filters_passes(self):
        assert notifier._job_passes_filters("개발", "정규직", [], []) is True

    def test_matching_duty(self):
        assert notifier._job_passes_filters("개발, 기획", "정규직", ["개발"], []) is True

    def test_non_matching_duty(self):
        assert notifier._job_passes_filters("기획", "정규직", ["개발"], []) is False

    def test_matching_work_type(self):
        assert notifier._job_passes_filters("개발", "정규직, 계약직", [], ["정규직"]) is True

    def test_non_matching_work_type(self):
        assert notifier._job_passes_filters("개발", "계약직", [], ["정규직"]) is False

    def test_none_duty_fails_filter(self):
        assert notifier._job_passes_filters(None, "정규직", ["개발"], []) is False

    def test_none_work_type_fails_filter(self):
        assert notifier._job_passes_filters("개발", None, [], ["정규직"]) is False

    def test_both_must_match(self):
        assert notifier._job_passes_filters("개발", "정규직", ["개발"], ["정규직"]) is True
        assert notifier._job_passes_filters("기획", "정규직", ["개발"], ["정규직"]) is False


class TestBuildNotificationPayload:
    def _make_row(self, **kwargs):
        base = {
            "id": 1,
            "title": "Test Title",
            "source_name": "sogang_job",
            "url": "http://example.com",
            "raw_content": "test content",
            "created_at": datetime(2024, 5, 1),
            "duty": None,
            "work_type": None,
            "deadline": None,
            "is_always_open": False,
        }
        base.update(kwargs)
        return base

    def test_basic_payload_built(self):
        rows = [self._make_row()]
        result = notifier._build_notification_payload(rows, [], [], [])
        assert len(result) == 1
        assert result[0]["title"] == "Test Title"
        assert result[0]["category_label"] == "채용공고"

    def test_keyword_filter_below_threshold(self):
        rows = [self._make_row(title="hello world", raw_content="nothing")]
        result = notifier._build_notification_payload(rows, [], [], ["python"])
        assert result == []

    def test_keyword_filter_above_threshold(self):
        rows = [self._make_row(title="python developer", raw_content="fastapi")]
        result = notifier._build_notification_payload(rows, [], [], ["python"])
        assert len(result) == 1

    def test_score_is_none_when_no_keywords(self):
        rows = [self._make_row()]
        result = notifier._build_notification_payload(rows, [], [], [])
        assert result[0]["score"] is None

    def test_score_set_when_keywords(self):
        rows = [self._make_row(title="python", raw_content="")]
        result = notifier._build_notification_payload(rows, [], [], ["python"])
        assert result[0]["score"] == 100

    def test_url_uses_site_base_url(self, monkeypatch):
        monkeypatch.setattr(notifier, "SITE_BASE_URL", "https://boonpick.com")
        rows = [self._make_row(id=42)]
        result = notifier._build_notification_payload(rows, [], [], [])
        assert result[0]["url"] == "https://boonpick.com/board/42"

    def test_url_falls_back_to_row_url(self, monkeypatch):
        monkeypatch.setattr(notifier, "SITE_BASE_URL", "")
        rows = [self._make_row(url="http://sogang.ac.kr/notice/1")]
        result = notifier._build_notification_payload(rows, [], [], [])
        assert result[0]["url"] == "http://sogang.ac.kr/notice/1"

    def test_job_duty_filter_excludes(self):
        rows = [self._make_row(duty="기획")]
        result = notifier._build_notification_payload(rows, ["개발"], [], [])
        assert result == []

    def test_apply_active_filter_excludes_expired(self):
        past = (datetime.now() - timedelta(days=400)).date()
        rows = [self._make_row(
            source_name="sogang_notice",
            created_at=datetime.now() - timedelta(days=400),
        )]
        result = notifier._build_notification_payload(rows, [], [], [], apply_active_filter=True)
        assert result == []

    def test_announcement_category_label(self):
        rows = [self._make_row(source_name="sogang_notice")]
        result = notifier._build_notification_payload(rows, [], [], [])
        assert result[0]["category_label"] == "학사공지"

    def test_scholarship_category_label(self):
        rows = [self._make_row(source_name="sogang_scholarship")]
        result = notifier._build_notification_payload(rows, [], [], [])
        assert result[0]["category_label"] == "장학금공지"


class TestNotifyNowForUser:
    def _make_cursor(self, user_row=None, content_rows=None):
        cursor = MagicMock()
        cursor.fetchone.return_value = user_row
        cursor.fetchall.return_value = content_rows or []
        return cursor

    def _make_conn(self, cursor):
        conn = MagicMock()
        conn.cursor.return_value = cursor
        return conn

    def test_raises_lookup_when_no_settings(self):
        cursor = self._make_cursor(user_row=None)
        conn = self._make_conn(cursor)
        with patch.object(notifier, "_db", return_value=conn):
            with pytest.raises(LookupError, match="알림 설정"):
                notifier.notify_now_for_user(999)

    def test_raises_lookup_when_no_email(self):
        cursor = self._make_cursor(user_row={
            "user_id": 1, "categories": "job", "duties": "", "work_types": "",
            "search_query": "", "keywords": "python", "email": None,
        })
        conn = self._make_conn(cursor)
        with patch.object(notifier, "_db", return_value=conn):
            with pytest.raises(LookupError, match="이메일"):
                notifier.notify_now_for_user(1)

    def test_raises_value_error_when_no_filters(self):
        cursor = self._make_cursor(user_row={
            "user_id": 1, "categories": "job", "duties": "", "work_types": "",
            "search_query": "", "keywords": "", "email": "u@ex.com",
        })
        conn = self._make_conn(cursor)
        with patch.object(notifier, "_db", return_value=conn):
            with pytest.raises(ValueError, match="키워드"):
                notifier.notify_now_for_user(1)

    def test_sends_mail_when_items_match(self):
        user = {
            "user_id": 1, "categories": "job", "duties": "", "work_types": "",
            "search_query": "", "keywords": "python", "email": "u@ex.com",
        }
        rows = [{
            "id": 10, "title": "python dev", "source_name": "sogang_job",
            "url": "http://ex.com/10", "raw_content": "python fastapi",
            "created_at": datetime.now(), "duty": None, "work_type": None,
            "deadline": None, "is_always_open": True,
        }]
        cursor = self._make_cursor(user_row=user, content_rows=rows)
        conn = self._make_conn(cursor)
        with patch.object(notifier, "_db", return_value=conn):
            with patch.object(notifier, "_fetch_all_active_items", return_value=rows):
                with patch("mailer.send_notification_email") as mock_mail:
                    result = notifier.notify_now_for_user(1)
        assert result >= 1
        mock_mail.assert_called_once()

    def test_returns_zero_when_no_matches(self):
        user = {
            "user_id": 1, "categories": "job", "duties": "", "work_types": "",
            "search_query": "", "keywords": "nonexistent_kw", "email": "u@ex.com",
        }
        cursor = self._make_cursor(user_row=user, content_rows=[])
        conn = self._make_conn(cursor)
        with patch.object(notifier, "_db", return_value=conn):
            with patch.object(notifier, "_fetch_all_active_items", return_value=[]):
                with patch("mailer.send_notification_email") as mock_mail:
                    result = notifier.notify_now_for_user(1)
        assert result == 0
        mock_mail.assert_not_called()


class TestNotifyNewItemsForAllUsers:
    def test_returns_count_of_sent_mails(self):
        users = [
            {"user_id": i, "categories": "job", "duties": "", "work_types": "",
             "search_query": "", "keywords": "python", "last_notified_at": datetime(2024, 1, 1),
             "email": f"user{i}@ex.com"}
            for i in range(3)
        ]
        rows = [{
            "id": 1, "title": "python dev", "source_name": "sogang_job",
            "url": "http://ex.com/1", "raw_content": "python",
            "created_at": datetime.now(), "duty": None, "work_type": None,
        }]
        cursor = MagicMock()
        cursor.fetchall.return_value = users
        conn = MagicMock()
        conn.cursor.return_value = cursor

        with patch.object(notifier, "_db", return_value=conn):
            with patch.object(notifier, "_fetch_new_items", return_value=rows):
                with patch("mailer.send_notification_email") as mock_mail:
                    result = notifier.notify_new_items_for_all_users()

        assert result == 3
        assert mock_mail.call_count == 3

    def test_skips_failed_user_continues_others(self):
        users = [
            {"user_id": 1, "categories": "job", "duties": "", "work_types": "",
             "search_query": "", "keywords": "python", "last_notified_at": datetime(2024, 1, 1),
             "email": "u1@ex.com"},
            {"user_id": 2, "categories": "job", "duties": "", "work_types": "",
             "search_query": "", "keywords": "python", "last_notified_at": datetime(2024, 1, 1),
             "email": "u2@ex.com"},
        ]
        rows = [{"id": 1, "title": "python", "source_name": "sogang_job",
                 "url": "http://ex.com", "raw_content": "python",
                 "created_at": datetime.now(), "duty": None, "work_type": None}]
        cursor = MagicMock()
        cursor.fetchall.return_value = users
        conn = MagicMock()
        conn.cursor.return_value = cursor

        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("DB error")

        with patch.object(notifier, "_db", return_value=conn):
            with patch.object(notifier, "_fetch_new_items", return_value=rows):
                with patch("mailer.send_notification_email", side_effect=side_effect):
                    result = notifier.notify_new_items_for_all_users()

        # second user still processes even though first failed
        assert result >= 0  # no crash

    def test_returns_zero_when_no_users(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value = cursor

        with patch.object(notifier, "_db", return_value=conn):
            result = notifier.notify_new_items_for_all_users()

        assert result == 0


# ── auto-generated: _db ──
class TestDb:
    def test_returns_mysql_connection(self, monkeypatch):
        monkeypatch.setenv("DB_HOST", "db.example.com")
        monkeypatch.setenv("DB_PORT", "3307")
        monkeypatch.setenv("DB_USER", "myuser")
        monkeypatch.setenv("DB_PASSWORD", "secret")
        monkeypatch.setenv("DB_NAME", "mydb")

        mock_conn = MagicMock()
        with patch("mysql.connector.connect", return_value=mock_conn) as mock_connect:
            result = notifier._db()

        mock_connect.assert_called_once_with(
            host="db.example.com",
            port=3307,
            user="myuser",
            password="secret",
            database="mydb",
        )
        assert result is mock_conn

    def test_uses_default_values_when_env_not_set(self, monkeypatch):
        for var in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"):
            monkeypatch.delenv(var, raising=False)

        mock_conn = MagicMock()
        with patch("mysql.connector.connect", return_value=mock_conn) as mock_connect:
            notifier._db()

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["host"] == "localhost"
        assert call_kwargs["port"] == 3306
        assert call_kwargs["user"] == "root"
        assert call_kwargs["password"] == ""
        assert call_kwargs["database"] == "boonpick"


# ── auto-generated: _fetch_new_items ──
class TestFetchNewItems:
    def _make_cursor(self, fetchall_return=None):
        cursor = MagicMock()
        cursor.fetchall.return_value = fetchall_return or []
        return cursor

    def test_returns_empty_list_when_no_matching_sources(self):
        cursor = self._make_cursor()
        # Pass an unknown/empty category so sources resolves to []
        result = notifier._fetch_new_items(cursor, datetime(2024, 1, 1), ["unknown_category"])
        assert result == []
        cursor.execute.assert_not_called()

    def test_executes_query_with_valid_categories(self):
        cursor = self._make_cursor(fetchall_return=[{"id": 1}])
        last_notified = datetime(2024, 1, 1)
        result = notifier._fetch_new_items(cursor, last_notified, ["announcement"])
        cursor.execute.assert_called_once()
        assert result == [{"id": 1}]

    def test_includes_search_filter_in_query_params(self):
        cursor = self._make_cursor(fetchall_return=[])
        last_notified = datetime(2024, 1, 1)
        notifier._fetch_new_items(cursor, last_notified, ["announcement"], search="장학금")
        call_args = cursor.execute.call_args
        params = call_args[0][1]
        assert any("장학금" in str(p) for p in params)

    def test_no_search_filter_when_search_is_empty(self):
        cursor = self._make_cursor(fetchall_return=[])
        last_notified = datetime(2024, 1, 1)
        notifier._fetch_new_items(cursor, last_notified, ["scholarship"], search="")
        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        assert "LIKE" not in sql

    def test_includes_last_notified_at_in_params(self):
        cursor = self._make_cursor(fetchall_return=[])
        last_notified = datetime(2024, 6, 15)
        notifier._fetch_new_items(cursor, last_notified, ["job"])
        call_args = cursor.execute.call_args
        params = call_args[0][1]
        assert last_notified in params

    def test_all_known_categories_map_to_sources(self):
        cursor = self._make_cursor(fetchall_return=[{"id": 99}])
        result = notifier._fetch_new_items(
            cursor, datetime(2024, 1, 1), ["announcement", "scholarship", "job"]
        )
        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        # All three sources should appear in params
        for src in ("sogang_notice", "sogang_scholarship", "sogang_job"):
            assert src in params

    def test_returns_fetchall_result(self):
        rows = [{"id": 1, "title": "Test"}, {"id": 2, "title": "Test2"}]
        cursor = self._make_cursor(fetchall_return=rows)
        result = notifier._fetch_new_items(cursor, datetime(2024, 1, 1), ["job"])
        assert result == rows


# ── auto-generated: _fetch_all_active_items ──
class TestFetchAllActiveItems:
    def _make_cursor(self, fetchall_return=None):
        cursor = MagicMock()
        cursor.fetchall.return_value = fetchall_return or []
        return cursor

    def test_returns_empty_list_when_no_matching_sources(self):
        cursor = self._make_cursor()
        result = notifier._fetch_all_active_items(cursor, ["unknown_category"])
        assert result == []
        cursor.execute.assert_not_called()

    def test_executes_query_with_valid_categories(self):
        cursor = self._make_cursor(fetchall_return=[{"id": 5}])
        result = notifier._fetch_all_active_items(cursor, ["job"])
        cursor.execute.assert_called_once()
        assert result == [{"id": 5}]

    def test_no_time_filter_in_query(self):
        cursor = self._make_cursor(fetchall_return=[])
        notifier._fetch_all_active_items(cursor, ["announcement"])
        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        assert "created_at >" not in sql

    def test_includes_search_filter_when_provided(self):
        cursor = self._make_cursor(fetchall_return=[])
        notifier._fetch_all_active_items(cursor, ["scholarship"], search="서울")
        call_args = cursor.execute.call_args
        params = call_args[0][1]
        assert any("서울" in str(p) for p in params)

    def test_no_search_filter_when_empty(self):
        cursor = self._make_cursor(fetchall_return=[])
        notifier._fetch_all_active_items(cursor, ["job"], search="")
        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        assert "LIKE" not in sql

    def test_selects_deadline_and_is_always_open(self):
        cursor = self._make_cursor(fetchall_return=[])
        notifier._fetch_all_active_items(cursor, ["job"])
        call_args = cursor.execute.call_args
        sql = call_args[0][0]
        assert "deadline" in sql
        assert "is_always_open" in sql

    def test_returns_fetchall_result(self):
        rows = [{"id": 10, "title": "A"}, {"id": 11, "title": "B"}]
        cursor = self._make_cursor(fetchall_return=rows)
        result = notifier._fetch_all_active_items(cursor, ["announcement"])
        assert result == rows
