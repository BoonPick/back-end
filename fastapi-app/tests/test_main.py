"""
FastAPI 앱 테스트

실행 방법 (fastapi-app/ 디렉토리에서):
    pytest tests/ -v
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from main import app

client = TestClient(app)


# ── GET / ────────────────────────────────────────────────────────

class TestReadIndex:
    def test_index_returns_html_file(self, tmp_path):
        """index.html 파일이 존재하면 200 반환"""
        html_file = tmp_path / "index.html"
        html_file.write_text("<html><body>boonpick</body></html>")

        with patch("main.FileResponse") as mock_fr:
            mock_fr.return_value = MagicMock(status_code=200)
            response = client.get("/")
            mock_fr.assert_called_once_with("templates/index.html")


# ── POST /crawl ───────────────────────────────────────────────────

class TestTriggerCrawl:
    def test_crawl_success_default_page(self):
        """기본값(page_count=1)으로 크롤링 성공"""
        with patch("main.crawl_notices", return_value=5) as mock_crawl:
            response = client.post("/crawl")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "saved_count": 5}
        mock_crawl.assert_called_once_with(page_count=1)

    def test_crawl_success_custom_page(self):
        """page_count 파라미터를 지정했을 때"""
        with patch("main.crawl_notices", return_value=12) as mock_crawl:
            response = client.post("/crawl?page_count=3")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "saved_count": 12}
        mock_crawl.assert_called_once_with(page_count=3)

    def test_crawl_no_new_notices(self):
        """새 공지가 없어서 0건 저장"""
        with patch("main.crawl_notices", return_value=0):
            response = client.post("/crawl")

        assert response.status_code == 200
        assert response.json()["saved_count"] == 0

    def test_crawl_exception_returns_500(self):
        """크롤링 중 예외 발생 시 500 반환"""
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


class TestGetContents:
    def _mock_db(self, rows):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn, mock_cursor

    def test_returns_list_of_contents(self):
        """DB에 데이터가 있으면 목록 반환"""
        rows = [make_mock_row(id=1), make_mock_row(id=2, title="두번째 공지")]
        mock_conn, _ = self._mock_db(rows)

        with patch("main.get_db_connection", return_value=mock_conn):
            response = client.get("/contents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[1]["title"] == "두번째 공지"

    def test_returns_empty_list_when_no_data(self):
        """DB가 비어있으면 빈 배열 반환"""
        mock_conn, _ = self._mock_db([])

        with patch("main.get_db_connection", return_value=mock_conn):
            response = client.get("/contents")

        assert response.status_code == 200
        assert response.json() == []

    def test_db_error_returns_500(self):
        """DB 오류 시 500 반환"""
        import mysql.connector

        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = mysql.connector.Error("DB 연결 실패")

        with patch("main.get_db_connection", return_value=mock_conn):
            response = client.get("/contents")

        assert response.status_code == 500

    def test_cursor_closed_after_request(self):
        """요청 완료 후 cursor와 connection이 반드시 close됨"""
        rows = [make_mock_row()]
        mock_conn, mock_cursor = self._mock_db(rows)

        with patch("main.get_db_connection", return_value=mock_conn):
            client.get("/contents")

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()


# ── crawling_noti 유틸리티 ────────────────────────────────────────

class TestExtractCategoryFromTitle:
    """extract_category_from_title 함수 단위 테스트"""

    def setup_method(self):
        from crawling_noti import extract_category_from_title
        self.fn = extract_category_from_title

    def test_extracts_bracket_category(self):
        category, title = self.fn("[장학] 2025년 장학생 모집")
        assert category == "장학"
        assert title == "2025년 장학생 모집"

    def test_no_bracket_returns_empty_category(self):
        category, title = self.fn("일반 공지사항입니다")
        assert category == ""
        assert title == "일반 공지사항입니다"

    def test_strips_whitespace(self):
        category, title = self.fn("[ 학사 ]  수강신청 안내")
        assert category == "학사"
        assert title == "수강신청 안내"

    def test_empty_string(self):
        category, title = self.fn("")
        assert category == ""
        assert title == ""

    def test_only_brackets(self):
        category, title = self.fn("[공지]")
        assert category == "공지"
        assert title == ""


# ── pdfviewer 유틸리티 ────────────────────────────────────────────

class TestToDownloadUrl:
    """to_download_url 함수 단위 테스트"""

    def setup_method(self):
        from pdfviewer import to_download_url
        self.fn = to_download_url

    def test_converts_viewer_url_to_download_url(self):
        viewer_url = (
            "https://scc.sogang.ac.kr/FileViewer?"
            "pathStr%3Dsome%2Fpath%26fileName%3Dtest.pdf%26gubun=cmsfile"
        )
        result = self.fn(viewer_url)
        assert "Download3" in result
        assert "pathStr=" in result

    def test_plain_url_returned_as_is(self):
        """pathStr이 없는 URL은 그대로 반환"""
        plain_url = "https://example.com/file.pdf"
        result = self.fn(plain_url)
        assert result == plain_url


class TestFindPdfUrls:
    """find_pdf_urls 함수 단위 테스트"""

    def setup_method(self):
        from pdfviewer import find_pdf_urls
        self.fn = find_pdf_urls

    def test_finds_pdf_link_in_html(self):
        html = '<a href="/files/notice.pdf">첨부파일</a>'
        urls = self.fn(html, {})
        assert len(urls) == 1
        assert "notice.pdf" in urls[0]

    def test_finds_pdf_in_api_filelist(self):
        html = ""
        api_data = {
            "fileList": [{"url": "https://example.com/attach.pdf"}]
        }
        urls = self.fn(html, api_data)
        assert any("attach.pdf" in u for u in urls)

    def test_no_pdf_returns_empty_list(self):
        html = "<p>첨부파일 없는 공지</p>"
        urls = self.fn(html, {})
        assert urls == []

    def test_deduplicates_same_url(self):
        html = (
            '<a href="/files/dup.pdf">파일1</a>'
            '<a href="/files/dup.pdf">파일2</a>'
        )
        urls = self.fn(html, {})
        assert urls.count(urls[0]) == 1
