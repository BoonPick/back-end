"""
main.py API 엔드포인트 테스트

실행: pytest tests/ -v
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime
import mysql.connector

from main import app

client = TestClient(app)


# ── GET / ────────────────────────────────────────────────────────

class TestReadIndex:
    def test_index_calls_file_response(self):
        with patch("main.FileResponse") as mock_fr:
            mock_fr.return_value = MagicMock(status_code=200)
            client.get("/")
            mock_fr.assert_called_once_with("templates/index.html")


# ── POST /crawl ───────────────────────────────────────────────────

class TestTriggerCrawl:
    def test_crawl_success_default_page(self):
        with patch("main.crawl_notices", return_value=5) as mock_crawl:
            response = client.post("/crawl")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "saved_count": 5}
        mock_crawl.assert_called_once_with(page_count=1)

    def test_crawl_success_custom_page(self):
        with patch("main.crawl_notices", return_value=12) as mock_crawl:
            response = client.post("/crawl?page_count=3")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "saved_count": 12}
        mock_crawl.assert_called_once_with(page_count=3)

    def test_crawl_no_new_notices(self):
        with patch("main.crawl_notices", return_value=0):
            response = client.post("/crawl")

        assert response.status_code == 200
        assert response.json()["saved_count"] == 0

    def test_crawl_exception_returns_500(self):
        with patch("main.crawl_notices", side_effect=Exception("네트워크 오류")):
            response = client.post("/crawl")

        assert response.status_code == 500
        assert "네트워크 오류" in response.json()["detail"]


# ── GET /contents ─────────────────────────────────────────────────

def make_mock_row(**kwargs):
    defaults = {
        "id": 1,
        "title": "테스트 공지",
        "source_name": "sogang_notice",
        "category": "일반",
        "url": "https://www.sogang.ac.kr/ko/notice?pkId=1",
        "raw_content": "공지 내용",
        "refined_content": None,
        "created_at": datetime(2026, 4, 1, 6, 0, 0),
        "updated_at": datetime(2026, 4, 1, 6, 0, 0),
    }
    return {**defaults, **kwargs}


def make_mock_db(rows):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


class TestGetContents:
    def test_returns_list_of_contents(self):
        rows = [make_mock_row(id=1), make_mock_row(id=2, title="두번째 공지")]
        mock_conn, _ = make_mock_db(rows)

        with patch("main.get_db_connection", return_value=mock_conn):
            response = client.get("/contents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["title"] == "두번째 공지"

    def test_returns_empty_list_when_no_data(self):
        mock_conn, _ = make_mock_db([])

        with patch("main.get_db_connection", return_value=mock_conn):
            response = client.get("/contents")

        assert response.status_code == 200
        assert response.json() == []

    def test_db_error_returns_500(self):
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = mysql.connector.Error("DB 연결 실패")

        with patch("main.get_db_connection", return_value=mock_conn):
            response = client.get("/contents")

        assert response.status_code == 500

    def test_cursor_closed_after_request(self):
        rows = [make_mock_row()]
        mock_conn, mock_cursor = make_mock_db(rows)

        with patch("main.get_db_connection", return_value=mock_conn):
            client.get("/contents")

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_cursor_closed_even_on_db_error(self):
        """cursor 할당 전 예외가 발생해도 conn은 반드시 close됨"""
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = mysql.connector.Error("커서 오류")

        with patch("main.get_db_connection", return_value=mock_conn):
            client.get("/contents")

        mock_conn.close.assert_called_once()
