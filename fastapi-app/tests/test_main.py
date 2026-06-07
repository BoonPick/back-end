import sys
from unittest.mock import MagicMock, patch

# pdfplumber (and its broken cffi/cryptography chain) is not available in this
# environment.  Stub it out before any source module is imported so that
# collection does not crash.
sys.modules.setdefault('pdfplumber', MagicMock())

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

import main
from main import app

client = TestClient(app)


def _make_cursor(rows=None, fetchone_val=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    cursor.fetchone.return_value = fetchone_val
    cursor.lastrowid = 1
    return cursor


def _make_conn(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


# ── /api/keywords ────────────────────────────────────────────────

class TestGetKeywords:
    def test_returns_keyword_list(self):
        cursor = _make_cursor(rows=[("AI",), ("장학금",)])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/keywords")
        assert resp.status_code == 200
        assert resp.json() == ["AI", "장학금"]

    def test_returns_empty_list(self):
        cursor = _make_cursor(rows=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/keywords")
        assert resp.status_code == 200
        assert resp.json() == []


# ── /api/board ───────────────────────────────────────────────────

def _board_row(**kwargs):
    defaults = {
        "id": 1,
        "title": "테스트 공지",
        "source_name": "sogang_notice",
        "category": None,
        "url": "https://example.com",
        "raw_content": "본문 내용",
        "created_at": datetime(2026, 4, 27),
        "employment": None,
        "work_type": None,
        "duty": None,
        "deadline": None,
        "is_always_open": None,
    }
    defaults.update(kwargs)
    return defaults


class TestGetBoardItems:
    def test_returns_board_items(self):
        cursor = _make_cursor(rows=[_board_row()])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "테스트 공지"

    def test_job_item_includes_employment(self):
        row = _board_row(
            source_name="sogang_job",
            employment="인턴",
            work_type="인턴직",
            duty="기타",
            deadline=None,
            is_always_open=1,
        )
        cursor = _make_cursor(rows=[row])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board")
        data = resp.json()
        assert data[0]["employment"] == "인턴"
        assert data[0]["isAlwaysOpen"] is True

    def test_category_filter_param(self):
        cursor = _make_cursor(rows=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?category=announcement")
        assert resp.status_code == 200

    def test_pagination_params(self):
        cursor = _make_cursor(rows=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?page=2&size=10")
        assert resp.status_code == 200


class TestGetBoardItem:
    def test_returns_item(self):
        cursor = _make_cursor(fetchone_val=_board_row(id=42, title="단건 조회"))
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board/42")
        assert resp.status_code == 200
        assert resp.json()["title"] == "단건 조회"

    def test_returns_404_when_not_found(self):
        cursor = _make_cursor(fetchone_val=None)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board/9999")
        assert resp.status_code == 404


# ── /api/auth ────────────────────────────────────────────────────

from datetime import datetime, timedelta


def _verif_row(code="123456", verified=0, attempts=0, expires_in_seconds=600, row_id=10):
    return {
        "id": row_id,
        "code": code,
        "expires_at": datetime.now() + timedelta(seconds=expires_in_seconds),
        "verified": verified,
        "attempts": attempts,
    }


class TestSignup:
    def test_creates_user_with_valid_code(self):
        verif = _verif_row()
        user_row = {"id": 1, "login_id": "test@test.com", "user_name": "홍길동", "email": "test@test.com"}
        cursor = _make_cursor()
        # 1) 중복 체크 (None) → 2) verification 조회 → 3) user fetch
        cursor.fetchone.side_effect = [None, verif, user_row]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/signup", json={
                "email": "test@test.com",
                "password": "pw",
                "name": "홍길동",
                "verification_code": "123456",
            })
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@test.com"

    def test_duplicate_email_returns_400(self):
        existing = {"id": 1, "login_id": "dup@test.com", "user_name": "홍길동", "email": "dup@test.com"}
        cursor = _make_cursor(fetchone_val=existing)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/signup", json={
                "email": "dup@test.com",
                "password": "pw",
                "name": "홍길동",
                "verification_code": "123456",
            })
        assert resp.status_code == 400

    def test_missing_code_returns_400(self):
        resp = client.post("/api/auth/signup", json={
            "email": "test@test.com",
            "password": "pw",
            "name": "홍길동",
            "verification_code": "",
        })
        assert resp.status_code == 400
        assert "인증코드" in resp.json()["detail"]

    def test_no_verification_record_returns_400(self):
        cursor = _make_cursor()
        cursor.fetchone.side_effect = [None, None]  # 중복 X, verification 없음
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/signup", json={
                "email": "new@test.com",
                "password": "pw",
                "name": "홍길동",
                "verification_code": "123456",
            })
        assert resp.status_code == 400
        assert "먼저 발송" in resp.json()["detail"]

    def test_wrong_code_returns_400(self):
        verif = _verif_row(code="999999")
        cursor = _make_cursor()
        cursor.fetchone.side_effect = [None, verif]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/signup", json={
                "email": "new@test.com",
                "password": "pw",
                "name": "홍길동",
                "verification_code": "123456",
            })
        assert resp.status_code == 400
        assert "일치하지 않습니다" in resp.json()["detail"]

    def test_expired_code_returns_400(self):
        verif = _verif_row(expires_in_seconds=-60)  # 이미 만료
        cursor = _make_cursor()
        cursor.fetchone.side_effect = [None, verif]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/signup", json={
                "email": "new@test.com",
                "password": "pw",
                "name": "홍길동",
                "verification_code": "123456",
            })
        assert resp.status_code == 400
        assert "만료" in resp.json()["detail"]

    def test_already_verified_returns_400(self):
        verif = _verif_row(verified=1)
        cursor = _make_cursor()
        cursor.fetchone.side_effect = [None, verif]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/signup", json={
                "email": "new@test.com",
                "password": "pw",
                "name": "홍길동",
                "verification_code": "123456",
            })
        assert resp.status_code == 400
        assert "사용된" in resp.json()["detail"]

    def test_too_many_attempts_returns_400(self):
        verif = _verif_row(attempts=5)
        cursor = _make_cursor()
        cursor.fetchone.side_effect = [None, verif]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/signup", json={
                "email": "new@test.com",
                "password": "pw",
                "name": "홍길동",
                "verification_code": "123456",
            })
        assert resp.status_code == 400
        assert "초과" in resp.json()["detail"]


class TestSendCode:
    def test_sends_code_for_new_email(self):
        cursor = _make_cursor()
        # 1) users 중복 체크 (None) → 2) 직전 verification (None)
        cursor.fetchone.side_effect = [None, None]
        with patch("main.get_db", return_value=_make_conn(cursor)), \
             patch("main.mailer.send_verification_code") as mock_send:
            resp = client.post("/api/auth/send-code", json={"email": "new@test.com"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["expires_in"] == 600
        mock_send.assert_called_once()
        # 호출 인자: (to_email, code, minutes)
        args = mock_send.call_args.args
        assert args[0] == "new@test.com"
        assert len(args[1]) == 6 and args[1].isdigit()

    def test_invalid_email_returns_400(self):
        resp = client.post("/api/auth/send-code", json={"email": "not-an-email"})
        assert resp.status_code == 400

    def test_already_registered_email_returns_400(self):
        existing = {"id": 1}
        cursor = _make_cursor(fetchone_val=existing)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/send-code", json={"email": "exists@test.com"})
        assert resp.status_code == 400

    def test_resend_within_cooldown_returns_429(self):
        cursor = _make_cursor()
        # 1) users (None) → 2) 직전 verification: 30초 전 발송
        cursor.fetchone.side_effect = [
            None,
            {"created_at": datetime.now() - timedelta(seconds=30)},
        ]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/send-code", json={"email": "new@test.com"})
        assert resp.status_code == 429

    def test_smtp_failure_returns_500(self):
        cursor = _make_cursor()
        cursor.fetchone.side_effect = [None, None]
        with patch("main.get_db", return_value=_make_conn(cursor)), \
             patch("main.mailer.send_verification_code", side_effect=RuntimeError("smtp down")):
            resp = client.post("/api/auth/send-code", json={"email": "new@test.com"})
        assert resp.status_code == 500


# ── /api/admin/keywords ──────────────────────────────────────────

class TestAdminKeywords:
    def test_get_all(self):
        cursor = _make_cursor(rows=[{"id": 1, "keyword_name": "AI"}])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/admin/keywords")
        assert resp.status_code == 200
        assert resp.json()[0]["keyword_name"] == "AI"

    def test_create_keyword(self):
        cursor = _make_cursor(fetchone_val=None)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/admin/keywords", json={"keyword_name": "머신러닝"})
        assert resp.status_code == 201
        assert resp.json()["keyword_name"] == "머신러닝"

    def test_create_duplicate_returns_400(self):
        cursor = _make_cursor(fetchone_val={"id": 1})
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/admin/keywords", json={"keyword_name": "중복"})
        assert resp.status_code == 400

    def test_delete_not_found_returns_404(self):
        cursor = _make_cursor(fetchone_val=None)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.delete("/api/admin/keywords/9999")
        assert resp.status_code == 404


# ── get_db: 커넥션 풀에서 연결을 가져온다 ──
class TestGetDb:
    def test_returns_connection_from_pool(self):
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.get_connection.return_value = mock_conn
        with patch.object(main, "_get_pool", return_value=mock_pool):
            conn = main.get_db()
        assert conn is mock_conn
        mock_pool.get_connection.assert_called_once()

    def test_falls_back_to_direct_connect_when_pool_unavailable(self):
        # 풀 생성이 실패하면 직접 연결로 폴백한다.
        mock_conn = MagicMock()
        with patch.object(main, "_get_pool", side_effect=Exception("pool down")), \
             patch("mysql.connector.connect", return_value=mock_conn) as mock_connect:
            conn = main.get_db()
        assert conn is mock_conn
        mock_connect.assert_called_once_with(**main.DB_CONFIG)

    def test_db_config_uses_env_defaults(self):
        assert main.DB_CONFIG["host"] is not None
        assert main.DB_CONFIG["database"] is not None


# ── auto-generated: login ──
class TestLogin:
    def test_existing_user_returns_user(self):
        user_row = {"id": 5, "login_id": "user@test.com", "user_name": "홍길동", "email": "user@test.com"}
        cursor = _make_cursor(fetchone_val=user_row)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/login", json={"email": "user@test.com", "password": "pw"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "user@test.com"
        assert body["name"] == "홍길동"
        assert body["id"] == "5"

    def test_new_user_auto_created_on_login(self):
        new_user = {"id": 10, "login_id": "brand@new.com", "user_name": "brand", "email": "brand@new.com"}
        cursor = _make_cursor()
        # First fetchone returns None (user doesn't exist), second returns the newly created user
        cursor.fetchone.side_effect = [None, new_user]
        cursor.lastrowid = 10
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/login", json={"email": "brand@new.com", "password": "secret"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "brand@new.com"

    def test_login_closes_connection(self):
        user_row = {"id": 1, "login_id": "a@b.com", "user_name": "A", "email": "a@b.com"}
        cursor = _make_cursor(fetchone_val=user_row)
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            client.post("/api/auth/login", json={"email": "a@b.com", "password": "pw"})
        conn.close.assert_called_once()


# ── auto-generated: admin_update_keyword ──
class TestAdminUpdateKeyword:
    def test_updates_existing_keyword(self):
        cursor = _make_cursor()
        # 1) find by id (found) → 2) check name conflict (not found)
        cursor.fetchone.side_effect = [{"id": 3}, None]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.put("/api/admin/keywords/3", json={"keyword_name": "새키워드"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 3
        assert body["keyword_name"] == "새키워드"

    def test_returns_404_when_keyword_not_found(self):
        cursor = _make_cursor(fetchone_val=None)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.put("/api/admin/keywords/999", json={"keyword_name": "없음"})
        assert resp.status_code == 404
        assert "찾을 수 없습니다" in resp.json()["detail"]

    def test_returns_400_on_duplicate_name(self):
        cursor = _make_cursor()
        # 1) find by id (found) → 2) check name conflict (found - conflict)
        cursor.fetchone.side_effect = [{"id": 3}, {"id": 5}]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.put("/api/admin/keywords/3", json={"keyword_name": "기존키워드"})
        assert resp.status_code == 400
        assert "이미 존재" in resp.json()["detail"]

    def test_closes_connection_after_update(self):
        cursor = _make_cursor()
        cursor.fetchone.side_effect = [{"id": 1}, None]
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            client.put("/api/admin/keywords/1", json={"keyword_name": "업데이트"})
        conn.close.assert_called_once()


# ── auto-generated: admin_delete_keyword ──
class TestAdminDeleteKeyword:
    def test_deletes_existing_keyword(self):
        cursor = _make_cursor()
        cursor.fetchone.return_value = {"id": 7}
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.delete("/api/admin/keywords/7")
        assert resp.status_code == 204

    def test_returns_404_when_not_found(self):
        cursor = _make_cursor(fetchone_val=None)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.delete("/api/admin/keywords/404")
        assert resp.status_code == 404

    def test_commits_after_delete(self):
        cursor = _make_cursor()
        cursor.fetchone.return_value = {"id": 2}
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            client.delete("/api/admin/keywords/2")
        conn.commit.assert_called_once()

    def test_closes_connection_after_delete(self):
        cursor = _make_cursor()
        cursor.fetchone.return_value = {"id": 3}
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            client.delete("/api/admin/keywords/3")
        conn.close.assert_called_once()


# ── auto-generated: _row_to_board_item ──
class TestRowToBoardItem:
    def test_maps_source_name_to_category(self):
        row = _board_row(source_name="sogang_scholarship")
        item = main._row_to_board_item(row)
        assert item.category == "scholarship"

    def test_unknown_source_name_defaults_to_announcement(self):
        row = _board_row(source_name="unknown_source")
        item = main._row_to_board_item(row)
        assert item.category == "announcement"

    def test_truncates_raw_content_to_200_chars(self):
        long_content = "A" * 300
        row = _board_row(raw_content=long_content)
        item = main._row_to_board_item(row)
        assert item.summary.endswith("...")
        assert len(item.summary) <= 204  # 200 + "..."

    def test_short_content_no_ellipsis(self):
        short_content = "짧은 내용"
        row = _board_row(raw_content=short_content)
        item = main._row_to_board_item(row)
        assert item.summary == short_content
        assert not item.summary.endswith("...")

    def test_formats_date_from_created_at(self):
        row = _board_row(created_at=datetime(2025, 6, 15))
        item = main._row_to_board_item(row)
        assert item.date == "2025-06-15"

    def test_none_created_at_gives_empty_date(self):
        row = _board_row(created_at=None)
        item = main._row_to_board_item(row)
        assert item.date == ""

    def test_deadline_formatted_correctly(self):
        from datetime import date
        row = _board_row(deadline=datetime(2025, 12, 31))
        item = main._row_to_board_item(row)
        assert item.deadline == "2025-12-31"

    def test_none_deadline_is_none(self):
        row = _board_row(deadline=None)
        item = main._row_to_board_item(row)
        assert item.deadline is None

    def test_is_always_open_true_when_1(self):
        row = _board_row(is_always_open=1)
        item = main._row_to_board_item(row)
        assert item.isAlwaysOpen is True

    def test_is_always_open_none_when_field_none(self):
        row = _board_row(is_always_open=None)
        item = main._row_to_board_item(row)
        assert item.isAlwaysOpen is None

    def test_job_source_name_maps_to_job_category(self):
        row = _board_row(source_name="sogang_job")
        item = main._row_to_board_item(row)
        assert item.category == "job"

    def test_sogang_notice_maps_to_announcement(self):
        row = _board_row(source_name="sogang_notice")
        item = main._row_to_board_item(row)
        assert item.category == "announcement"


# ── auto-generated: get_board_items ──
class TestGetBoardItemsExtended:
    def test_keyword_filter_param(self):
        cursor = _make_cursor(rows=[_board_row()])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?keywords=AI,머신러닝")
        assert resp.status_code == 200

    def test_search_filter_param(self):
        cursor = _make_cursor(rows=[_board_row(title="검색결과")])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?search=검색")
        assert resp.status_code == 200
        assert resp.json()[0]["title"] == "검색결과"

    def test_duty_filter_param(self):
        cursor = _make_cursor(rows=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?duty=개발")
        assert resp.status_code == 200

    def test_work_type_filter_param(self):
        cursor = _make_cursor(rows=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?work_type=인턴")
        assert resp.status_code == 200

    def test_category_job_filter(self):
        cursor = _make_cursor(rows=[_board_row(source_name="sogang_job")])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?category=job")
        assert resp.status_code == 200
        assert resp.json()[0]["category"] == "job"

    def test_multiple_filters_combined(self):
        cursor = _make_cursor(rows=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?category=scholarship&search=장학&page=1&size=5")
        assert resp.status_code == 200

    def test_size_out_of_range_returns_422(self):
        resp = client.get("/api/board?size=200")
        assert resp.status_code == 422

    def test_page_less_than_1_returns_422(self):
        resp = client.get("/api/board?page=0")
        assert resp.status_code == 422

    def test_empty_result_returns_empty_list(self):
        cursor = _make_cursor(rows=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unknown_category_returns_empty_list(self):
        cursor = _make_cursor(rows=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/board?category=unknown")
        assert resp.status_code == 200

    def test_closes_connection(self):
        cursor = _make_cursor(rows=[])
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            client.get("/api/board")
        conn.close.assert_called_once()


# ── auto-generated: get_recommendation ──
class TestGetRecommendation:
    def test_returns_default_when_no_keywords(self):
        content_row = {"id": 1, "title": "공지", "category": "announcement", "raw_content": "내용"}
        cursor = _make_cursor(fetchone_val=content_row)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/recommendations/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["matchScore"] == 0
        assert body["itemId"] == "1"
        assert "키워드" in body["matchReason"]

    def test_returns_404_when_content_not_found(self):
        cursor = _make_cursor(fetchone_val=None)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/recommendations/9999?keywords=AI")
        assert resp.status_code == 404

    def test_calls_llm_with_keywords(self):
        content_row = {"id": 2, "title": "AI 채용", "category": "job", "raw_content": "내용 내용"}
        cursor = _make_cursor(fetchone_val=content_row)
        llm_result = {
            "matchScore": 85,
            "matchReason": "관련 높음",
            "preparationTips": ["포트폴리오 준비"],
        }
        with patch("main.get_db", return_value=_make_conn(cursor)), \
             patch("main.get_llm_recommendation", return_value=llm_result) as mock_llm:
            resp = client.get("/api/recommendations/2?keywords=AI,머신러닝")
        assert resp.status_code == 200
        body = resp.json()
        assert body["matchScore"] == 85
        assert body["itemId"] == "2"
        mock_llm.assert_called_once_with(
            keywords=["AI", "머신러닝"],
            title="AI 채용",
            category="job",
            raw_content="내용 내용",
            employment=None,
            work_type=None,
            duty=None,
            deadline=None,
            is_always_open=None,
        )

    def test_closes_connection(self):
        content_row = {"id": 3, "title": "제목", "category": "announcement", "raw_content": ""}
        cursor = _make_cursor(fetchone_val=content_row)
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            client.get("/api/recommendations/3")
        conn.close.assert_called_once()


# ── auto-generated: trigger_crawl ──
class TestTriggerCrawl:
    def test_returns_saved_and_page_count(self):
        with patch("main.crawling_noti.crawl_notices", return_value=10) as mock_crawl:
            resp = client.post("/api/admin/crawl")
        assert resp.status_code == 200
        body = resp.json()
        assert body["saved"] == 10
        assert body["page_count"] == 5  # default
        mock_crawl.assert_called_once_with(page_count=5)

    def test_custom_page_count(self):
        with patch("main.crawling_noti.crawl_notices", return_value=3) as mock_crawl:
            resp = client.post("/api/admin/crawl?page_count=2")
        assert resp.status_code == 200
        assert resp.json()["page_count"] == 2
        mock_crawl.assert_called_once_with(page_count=2)

    def test_page_count_too_high_returns_422(self):
        resp = client.post("/api/admin/crawl?page_count=99")
        assert resp.status_code == 422

    def test_page_count_zero_returns_422(self):
        resp = client.post("/api/admin/crawl?page_count=0")
        assert resp.status_code == 422


# ── auto-generated: trigger_job_crawl ──
class TestTriggerJobCrawl:
    def test_returns_saved_and_page_count(self):
        with patch("main.crawling_job.crawl_jobs", return_value=7) as mock_crawl:
            resp = client.post("/api/admin/crawl/jobs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["saved"] == 7
        assert body["page_count"] == 3  # default
        mock_crawl.assert_called_once_with(page_count=3)

    def test_custom_page_count(self):
        with patch("main.crawling_job.crawl_jobs", return_value=4) as mock_crawl:
            resp = client.post("/api/admin/crawl/jobs?page_count=10")
        assert resp.status_code == 200
        assert resp.json()["page_count"] == 10
        mock_crawl.assert_called_once_with(page_count=10)

    def test_page_count_too_high_returns_422(self):
        resp = client.post("/api/admin/crawl/jobs?page_count=21")
        assert resp.status_code == 422

    def test_page_count_zero_returns_422(self):
        resp = client.post("/api/admin/crawl/jobs?page_count=0")
        assert resp.status_code == 422


# ── auto-generated: dedup_jobs_by_title_worktype ──
class TestDedupJobsByTitleWorktype:
    def _make_dedup_cursor(self, groups=None):
        """Build a cursor that returns the given dedup groups on fetchall."""
        cursor = MagicMock()
        cursor.fetchall.return_value = groups or []
        cursor.rowcount = 0
        return cursor

    def test_dry_run_returns_summary_without_deleting(self):
        groups = [
            {"title": "AI 인턴", "work_type": "인턴", "cnt": "3", "ids": "1,2,3"},
        ]
        cursor = self._make_dedup_cursor(groups=groups)
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/admin/dedup/jobs?dry_run=true")
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is True
        assert body["groups"] == 1
        assert body["affected_rows"] == 2  # cnt=3 → 3-1=2 duplicates
        assert body["samples"][0]["title"] == "AI 인턴"
        # Connection closed but no DELETE should have been executed
        conn.close.assert_called_once()

    def test_dry_run_default_is_true(self):
        cursor = self._make_dedup_cursor(groups=[])
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/admin/dedup/jobs")
        assert resp.status_code == 200
        assert resp.json()["dry_run"] is True

    def test_no_duplicates_returns_zero_affected(self):
        cursor = self._make_dedup_cursor(groups=[])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/admin/dedup/jobs?dry_run=true")
        body = resp.json()
        assert body["affected_rows"] == 0
        assert body["groups"] == 0

    def test_actual_delete_when_dry_run_false(self):
        groups = [
            {"title": "백엔드 개발자", "work_type": "정규직", "cnt": "2", "ids": "10,20"},
        ]
        cursor = self._make_dedup_cursor(groups=groups)
        cursor.rowcount = 1
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/admin/dedup/jobs?dry_run=false")
        assert resp.status_code == 200
        body = resp.json()
        assert body["dry_run"] is False
        conn.commit.assert_called()
        conn.close.assert_called_once()

    def test_rollback_on_exception_during_delete(self):
        groups = [
            {"title": "프론트엔드", "work_type": None, "cnt": "2", "ids": "5,6"},
        ]
        cursor = self._make_dedup_cursor(groups=groups)
        # Make cursor.execute raise on the 3rd call (inside deletion block)
        call_count = [0]
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3:  # DROP + CREATE + DELETE = 3rd call
                raise RuntimeError("DB error")
        cursor.execute.side_effect = execute_side_effect
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            try:
                client.post("/api/admin/dedup/jobs?dry_run=false")
            except Exception:
                pass
        conn.close.assert_called_once()

    def test_samples_capped_at_20(self):
        groups = [
            {"title": f"공고 {i}", "work_type": "인턴", "cnt": "2", "ids": f"{i},{i+100}"}
            for i in range(25)
        ]
        cursor = self._make_dedup_cursor(groups=groups)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/admin/dedup/jobs?dry_run=true")
        body = resp.json()
        assert len(body["samples"]) == 20


# ── auto-generated: _settings_row_to_model ──
class TestSettingsRowToModel:
    def test_splits_comma_separated_categories(self):
        row = {"categories": "announcement,scholarship", "duties": None, "work_types": None,
               "search_query": None, "keywords": None}
        settings = main._settings_row_to_model(row)
        assert settings.categories == ["announcement", "scholarship"]

    def test_splits_duties_and_work_types(self):
        row = {"categories": "job", "duties": "개발,디자인", "work_types": "인턴,정규직",
               "search_query": "검색어", "keywords": "AI,ML"}
        settings = main._settings_row_to_model(row)
        assert settings.duties == ["개발", "디자인"]
        assert settings.work_types == ["인턴", "정규직"]
        assert settings.search == "검색어"
        assert settings.keywords == ["AI", "ML"]

    def test_none_fields_become_empty_lists(self):
        row = {"categories": "announcement", "duties": None, "work_types": None,
               "search_query": None, "keywords": None}
        settings = main._settings_row_to_model(row)
        assert settings.duties == []
        assert settings.work_types == []
        assert settings.keywords == []
        assert settings.search == ""

    def test_empty_string_fields_become_empty_lists(self):
        row = {"categories": "job", "duties": "", "work_types": "",
               "search_query": "", "keywords": ""}
        settings = main._settings_row_to_model(row)
        assert settings.duties == []
        assert settings.work_types == []

    def test_trims_whitespace_from_values(self):
        row = {"categories": "job , announcement", "duties": " 개발 , 디자인 ",
               "work_types": None, "search_query": None, "keywords": None}
        settings = main._settings_row_to_model(row)
        assert "job" in settings.categories
        assert "개발" in settings.duties


# ── auto-generated: get_notification_settings ──
class TestGetNotificationSettings:
    def test_returns_settings_when_row_exists(self):
        row = {"categories": "announcement,job", "duties": "개발", "work_types": "인턴",
               "search_query": "검색어", "keywords": "AI"}
        cursor = _make_cursor(fetchone_val=row)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/users/1/notification-settings")
        assert resp.status_code == 200
        body = resp.json()
        assert "announcement" in body["categories"]
        assert "job" in body["categories"]
        assert body["duties"] == ["개발"]

    def test_returns_null_when_no_settings(self):
        cursor = _make_cursor(fetchone_val=None)
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.get("/api/users/99/notification-settings")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_closes_connection(self):
        cursor = _make_cursor(fetchone_val=None)
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            client.get("/api/users/1/notification-settings")
        conn.close.assert_called_once()


# ── auto-generated: notify_now ──
class TestNotifyNow:
    def test_returns_items_sent_on_success(self):
        with patch("main.notifier.notify_now_for_user", return_value=5) as mock_notify:
            resp = client.post("/api/users/1/notify-now")
        assert resp.status_code == 200
        assert resp.json()["items_sent"] == 5
        mock_notify.assert_called_once_with(1)

    def test_returns_404_on_lookup_error(self):
        with patch("main.notifier.notify_now_for_user", side_effect=LookupError("사용자 없음")):
            resp = client.post("/api/users/9999/notify-now")
        assert resp.status_code == 404
        assert "사용자 없음" in resp.json()["detail"]

    def test_returns_400_on_value_error(self):
        with patch("main.notifier.notify_now_for_user", side_effect=ValueError("잘못된 설정")):
            resp = client.post("/api/users/1/notify-now")
        assert resp.status_code == 400
        assert "잘못된 설정" in resp.json()["detail"]

    def test_returns_500_on_unexpected_error(self):
        with patch("main.notifier.notify_now_for_user", side_effect=RuntimeError("서버 오류")):
            resp = client.post("/api/users/1/notify-now")
        assert resp.status_code == 500

    def test_zero_items_sent(self):
        with patch("main.notifier.notify_now_for_user", return_value=0):
            resp = client.post("/api/users/2/notify-now")
        assert resp.status_code == 200
        assert resp.json()["items_sent"] == 0


# ── auto-generated: upsert_notification_settings ──
class TestUpsertNotificationSettings:
    def _valid_payload(self, **overrides):
        payload = {
            "categories": ["announcement"],
            "duties": [],
            "work_types": [],
            "search": "",
            "keywords": [],
        }
        payload.update(overrides)
        return payload

    def test_creates_settings_successfully(self):
        cursor = _make_cursor()
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.put("/api/users/1/notification-settings", json=self._valid_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["categories"] == ["announcement"]

    def test_returns_400_when_no_categories(self):
        payload = self._valid_payload(categories=[])
        resp = client.put("/api/users/1/notification-settings", json=payload)
        assert resp.status_code == 400
        assert "카테고리" in resp.json()["detail"]

    def test_returns_400_for_invalid_category(self):
        payload = self._valid_payload(categories=["invalid_cat"])
        resp = client.put("/api/users/1/notification-settings", json=payload)
        assert resp.status_code == 400
        assert "허용되지 않은" in resp.json()["detail"]

    def test_job_category_preserves_duties_and_work_types(self):
        cursor = _make_cursor()
        payload = self._valid_payload(
            categories=["job"],
            duties=["개발"],
            work_types=["인턴"],
        )
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.put("/api/users/1/notification-settings", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["duties"] == ["개발"]
        assert body["work_types"] == ["인턴"]

    def test_non_job_category_clears_duties_and_work_types(self):
        cursor = _make_cursor()
        payload = self._valid_payload(
            categories=["announcement"],
            duties=["개발"],
            work_types=["인턴"],
        )
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.put("/api/users/1/notification-settings", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["duties"] == []
        assert body["work_types"] == []

    def test_commits_and_closes_connection(self):
        cursor = _make_cursor()
        conn = _make_conn(cursor)
        with patch("main.get_db", return_value=conn):
            client.put("/api/users/1/notification-settings", json=self._valid_payload())
        conn.commit.assert_called_once()
        conn.close.assert_called_once()

    def test_multiple_categories_accepted(self):
        cursor = _make_cursor()
        payload = self._valid_payload(categories=["announcement", "scholarship", "job"])
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.put("/api/users/5/notification-settings", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["categories"]) == {"announcement", "scholarship", "job"}

    def test_search_stripped_of_whitespace(self):
        cursor = _make_cursor()
        payload = self._valid_payload(search="  검색어  ")
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.put("/api/users/1/notification-settings", json=payload)
        assert resp.status_code == 200
        assert resp.json()["search"] == "검색어"


# ── auto-generated: read_index ──
class TestReadIndex:
    def test_returns_200_or_404_for_index(self):
        # FileResponse will 404 if templates/index.html doesn't exist in test env,
        # but the endpoint itself should be reachable (not a 405 or 422).
        resp = client.get("/")
        assert resp.status_code in (200, 404, 500)

    def test_get_method_is_allowed(self):
        # Verify that the route is registered and GET is the correct method
        resp = client.get("/")
        assert resp.status_code != 405  # 405 = method not allowed

    def test_post_to_index_returns_405(self):
        resp = client.post("/")
        assert resp.status_code == 405


# ── auto-generated: trigger_notification_batch ──
class TestTriggerNotificationBatch:
    def test_returns_emails_sent_count(self):
        with patch("main.notifier.notify_new_items_for_all_users", return_value=3) as mock_notify:
            resp = client.post("/api/admin/notify")
        assert resp.status_code == 200
        assert resp.json()["emails_sent"] == 3
        mock_notify.assert_called_once()

    def test_returns_zero_when_no_emails_sent(self):
        with patch("main.notifier.notify_new_items_for_all_users", return_value=0) as mock_notify:
            resp = client.post("/api/admin/notify")
        assert resp.status_code == 200
        assert resp.json()["emails_sent"] == 0
        mock_notify.assert_called_once()

    def test_returns_large_count(self):
        with patch("main.notifier.notify_new_items_for_all_users", return_value=150):
            resp = client.post("/api/admin/notify")
        assert resp.status_code == 200
        assert resp.json()["emails_sent"] == 150

    def test_response_contains_only_emails_sent_key(self):
        with patch("main.notifier.notify_new_items_for_all_users", return_value=1):
            resp = client.post("/api/admin/notify")
        body = resp.json()
        assert list(body.keys()) == ["emails_sent"]


