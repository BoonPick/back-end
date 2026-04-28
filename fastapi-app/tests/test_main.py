import pytest
from unittest.mock import MagicMock, patch
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
