"""
통합 테스트: FastAPI TestClient로 실제 HTTP 요청/응답 전체 스택을 검증합니다.

유닛 테스트와의 차이:
  - 실제 HTTP 라우팅·직렬화·검증(Pydantic)·상태코드가 모두 동작
  - DB 커넥션만 mock하여 네트워크 의존성 제거
  - 응답 JSON 구조가 바뀌면 즉시 실패 → 이메일 인증 추가 등 플로우 변경 탐지
"""

import pytest
from unittest.mock import MagicMock, patch, call
from fastapi.testclient import TestClient
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main import app

client = TestClient(app)


# ── fixtures ──────────────────────────────────────────────────────────────────

def mock_conn(fetchone=None, fetchall=None, lastrowid=1):
    conn = MagicMock()
    cur  = MagicMock()
    cur.fetchone.return_value  = fetchone
    cur.fetchall.return_value  = fetchall or []
    cur.lastrowid              = lastrowid
    conn.cursor.return_value   = cur
    return conn, cur


USER_ROW = {
    "id": 1,
    "login_id": "test@boonpick.com",
    "user_name": "테스트유저",
    "email": "test@boonpick.com",
    "password": "pw",
}

BOARD_ROW = {
    "id": 1,
    "title": "2026년 1학기 장학금 안내",
    "raw_content": "장학금 신청 기간은 3월 1일부터 3월 31일까지입니다.",
    "source_name": "sogang_scholarship",
    "url": "https://example.com/scholarship/1",
    "created_at": datetime(2026, 4, 1),
}


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestSignupIntegration:
    def test_성공시_user_응답_구조_검증(self):
        """응답 필드(id, email, name, keywords)가 모두 존재해야 함"""
        conn, cur = mock_conn(lastrowid=5)
        cur.fetchone.side_effect = [None, USER_ROW]  # 중복 없음 → 생성 후 조회

        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/auth/signup", json={
                "email": "test@boonpick.com",
                "password": "pw123",
                "name": "테스트유저",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "id"       in data, "id 필드 없음"
        assert "email"    in data, "email 필드 없음"
        assert "name"     in data, "name 필드 없음"
        assert "keywords" in data, "keywords 필드 없음"
        assert data["email"] == "test@boonpick.com"
        assert data["name"]  == "테스트유저"

    def test_중복_이메일_400_반환(self):
        conn, cur = mock_conn(fetchone=USER_ROW)

        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/auth/signup", json={
                "email": "test@boonpick.com",
                "password": "pw123",
                "name": "중복유저",
            })

        assert resp.status_code == 400
        assert "detail" in resp.json()

    def test_필드_누락시_422_반환(self):
        """Pydantic 검증 실패 → 422 Unprocessable Entity"""
        resp = client.post("/api/auth/signup", json={"email": "only@email.com"})
        assert resp.status_code == 422

    def test_이메일_형식_검증_없음_문자열_수용(self):
        """백엔드 email 필드는 str 타입 → 형식 검증 없이 수용 (프론트 type=email로만 제한)"""
        conn, cur = mock_conn(lastrowid=5)
        cur.fetchone.side_effect = [None, USER_ROW]
        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/auth/signup", json={
                "email": "not-an-email",
                "password": "pw",
                "name": "name",
            })
        # 422가 아닌 200 → 이메일 형식 서버 검증이 없다는 것을 문서화
        # EmailStr 도입 시 이 테스트가 실패하여 변경을 탐지
        assert resp.status_code == 200

    def test_응답_content_type_json(self):
        conn, cur = mock_conn()
        cur.fetchone.side_effect = [None, USER_ROW]
        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/auth/signup", json={
                "email": "t@t.com", "password": "pw", "name": "t"
            })
        assert "application/json" in resp.headers["content-type"]


class TestLoginIntegration:
    def test_성공시_user_응답(self):
        conn, cur = mock_conn(fetchone=USER_ROW)
        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/auth/login", json={
                "email": "test@boonpick.com",
                "password": "pw123",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@boonpick.com"

    def test_존재하지_않는_계정_자동_생성(self):
        """현재 스펙: 없는 계정이면 자동 생성"""
        conn, cur = mock_conn(lastrowid=99)
        cur.fetchone.side_effect = [None, USER_ROW]
        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/auth/login", json={
                "email": "new@boonpick.com",
                "password": "pw",
            })
        assert resp.status_code == 200

    def test_필드_누락시_422(self):
        resp = client.post("/api/auth/login", json={"email": "only@email.com"})
        assert resp.status_code == 422


# ── Keywords ──────────────────────────────────────────────────────────────────

class TestKeywordsIntegration:
    def test_키워드_목록_반환_구조(self):
        conn, cur = mock_conn(fetchall=[("AI",), ("장학금",), ("취업",)])
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/keywords")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert "AI" in data

    def test_빈_키워드_목록(self):
        conn, cur = mock_conn(fetchall=[])
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/keywords")
        assert resp.status_code == 200
        assert resp.json() == []


class TestAdminKeywordsIntegration:
    def test_admin_키워드_생성_201(self):
        conn, cur = mock_conn(lastrowid=10)
        cur.fetchone.return_value = None  # 중복 없음
        with patch("main.get_db", return_value=conn):
            resp = client.post("/api/admin/keywords", json={"keyword_name": "인공지능"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["keyword_name"] == "인공지능"
        assert "id" in data

    def test_admin_키워드_수정_200(self):
        conn, cur = mock_conn()
        cur.fetchone.side_effect = [{"id": 1}, None]  # 존재함, 중복 없음
        with patch("main.get_db", return_value=conn):
            resp = client.put("/api/admin/keywords/1", json={"keyword_name": "머신러닝"})
        assert resp.status_code == 200
        assert resp.json()["keyword_name"] == "머신러닝"

    def test_admin_없는_키워드_수정_404(self):
        conn, cur = mock_conn(fetchone=None)
        with patch("main.get_db", return_value=conn):
            resp = client.put("/api/admin/keywords/999", json={"keyword_name": "x"})
        assert resp.status_code == 404

    def test_admin_키워드_삭제_204(self):
        conn, cur = mock_conn(fetchone={"id": 1})
        with patch("main.get_db", return_value=conn):
            resp = client.delete("/api/admin/keywords/1")
        assert resp.status_code == 204

    def test_admin_없는_키워드_삭제_404(self):
        conn, cur = mock_conn(fetchone=None)
        with patch("main.get_db", return_value=conn):
            resp = client.delete("/api/admin/keywords/999")
        assert resp.status_code == 404


# ── Board ─────────────────────────────────────────────────────────────────────

class TestBoardIntegration:
    def test_게시글_목록_반환_구조(self):
        conn, cur = mock_conn(fetchall=[BOARD_ROW])
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/board")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        item = data[0]
        # 응답 구조가 변경되면 여기서 즉시 실패
        for field in ("id", "category", "title", "summary", "body", "source", "sourceUrl", "date", "keywords"):
            assert field in item, f"응답에 {field} 필드 없음"

    def test_카테고리_필터_파라미터_전달(self):
        conn, cur = mock_conn(fetchall=[])
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/board?category=scholarship")
        assert resp.status_code == 200

    def test_키워드_필터_파라미터_전달(self):
        conn, cur = mock_conn(fetchall=[BOARD_ROW])
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/board?keywords=장학금,AI")
        assert resp.status_code == 200

    def test_단일_게시글_조회(self):
        conn, cur = mock_conn(fetchone=BOARD_ROW)
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/board/1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "1"

    def test_없는_게시글_404(self):
        conn, cur = mock_conn(fetchone=None)
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/board/9999")
        assert resp.status_code == 404

    def test_페이지네이션_파라미터(self):
        conn, cur = mock_conn(fetchall=[])
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/board?page=2&size=10")
        assert resp.status_code == 200

    def test_잘못된_페이지_파라미터_422(self):
        resp = client.get("/api/board?page=0")  # ge=1 제약
        assert resp.status_code == 422


# ── Recommendation ────────────────────────────────────────────────────────────

class TestRecommendationIntegration:
    def test_키워드_없을때_기본_응답_구조(self):
        conn, cur = mock_conn(fetchone=BOARD_ROW)
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/recommendations/1?keywords=")
        assert resp.status_code == 200
        data = resp.json()
        for field in ("itemId", "matchScore", "matchReason", "preparationTips"):
            assert field in data, f"응답에 {field} 필드 없음"
        assert data["matchScore"] == 0

    def test_없는_게시글_404(self):
        conn, cur = mock_conn(fetchone=None)
        with patch("main.get_db", return_value=conn):
            resp = client.get("/api/recommendations/9999")
        assert resp.status_code == 404
