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

class TestSignup:
    def test_creates_user(self):
        user_row = {"id": 1, "login_id": "test@test.com", "user_name": "홍길동", "email": "test@test.com"}
        cursor = _make_cursor(fetchone_val=None)
        cursor.fetchone.side_effect = [None, user_row]
        with patch("main.get_db", return_value=_make_conn(cursor)):
            resp = client.post("/api/auth/signup", json={
                "email": "test@test.com",
                "password": "pw",
                "name": "홍길동",
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
            })
        assert resp.status_code == 400


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
