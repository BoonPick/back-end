"""
pdfviewer.py 테스트
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open

from pdfviewer import to_download_url, find_pdf_urls, download_pdf, extract_pdf_text


# ── to_download_url ───────────────────────────────────────────────

class TestToDownloadUrl:
    def test_converts_viewer_url_with_filename(self):
        url = (
            "https://scc.sogang.ac.kr/FileViewer?"
            "pathStr%3Dsome%2Fpath%26fileName%3Dtest.pdf%26gubun=cmsfile"
        )
        result = to_download_url(url)
        assert "Download3" in result
        assert "pathStr=" in result
        assert "fileName=" in result

    def test_converts_viewer_url_without_filename(self):
        url = (
            "https://scc.sogang.ac.kr/FileViewer?"
            "pathStr%3Dsome%2Fpath%26gubun=cmsfile"
        )
        result = to_download_url(url)
        assert "Download3" in result
        assert "pathStr=" in result

    def test_plain_url_returned_as_is(self):
        plain = "https://example.com/file.pdf"
        assert to_download_url(plain) == plain

    def test_empty_string_returned_as_is(self):
        assert to_download_url("") == ""

    def test_output_starts_with_download_base(self):
        url = (
            "https://scc.sogang.ac.kr/view?"
            "pathStr%3Dabc%26fileName%3Ddoc.pdf%26gubun=x"
        )
        result = to_download_url(url)
        assert result.startswith("https://scc.sogang.ac.kr/Download3")


# ── find_pdf_urls ─────────────────────────────────────────────────

class TestFindPdfUrls:
    def test_finds_pdf_link_in_anchor(self):
        html = '<a href="/files/notice.pdf">첨부파일</a>'
        urls = find_pdf_urls(html, {})
        assert len(urls) == 1
        assert "notice.pdf" in urls[0]

    def test_finds_pdf_in_iframe(self):
        html = '<iframe src="/view/sample.pdf"></iframe>'
        urls = find_pdf_urls(html, {})
        assert any("sample.pdf" in u for u in urls)

    def test_finds_pdf_in_embed(self):
        html = '<embed src="/docs/attach.pdf" />'
        urls = find_pdf_urls(html, {})
        assert any("attach.pdf" in u for u in urls)

    def test_finds_pdf_in_api_filelist(self):
        html = ""
        api_data = {"fileList": [{"url": "https://example.com/attach.pdf"}]}
        urls = find_pdf_urls(html, api_data)
        assert any("attach.pdf" in u for u in urls)

    def test_finds_pdf_in_attach_files(self):
        html = ""
        api_data = {"attachFiles": [{"fileUrl": "https://example.com/report.pdf"}]}
        urls = find_pdf_urls(html, api_data)
        assert any("report.pdf" in u for u in urls)

    def test_no_pdf_returns_empty_list(self):
        html = "<p>첨부파일 없는 공지</p>"
        urls = find_pdf_urls(html, {})
        assert urls == []

    def test_deduplicates_same_url(self):
        html = (
            '<a href="/files/dup.pdf">파일1</a>'
            '<a href="/files/dup.pdf">파일2</a>'
        )
        urls = find_pdf_urls(html, {})
        assert len(urls) == 1

    def test_relative_url_converted_to_absolute(self):
        html = '<a href="/files/doc.pdf">파일</a>'
        urls = find_pdf_urls(html, {})
        assert urls[0].startswith("http")

    def test_absolute_url_preserved(self):
        html = '<a href="https://external.com/file.pdf">파일</a>'
        urls = find_pdf_urls(html, {})
        assert urls[0].startswith("https://external.com")

    def test_download_url_detected_by_keyword(self):
        html = '<a href="/Download?pathStr=abc">다운로드</a>'
        urls = find_pdf_urls(html, {})
        assert len(urls) == 1


# ── download_pdf ──────────────────────────────────────────────────

class TestDownloadPdf:
    def _make_response(self, content=b"%PDF-1.4 fake content", content_type="application/pdf"):
        mock_resp = MagicMock()
        mock_resp.content = content
        mock_resp.headers = {"Content-Type": content_type}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_writes_pdf_to_file(self, tmp_path):
        save_path = str(tmp_path / "test.pdf")
        mock_resp = self._make_response()

        with patch("pdfviewer.requests.get", return_value=mock_resp):
            download_pdf("https://example.com/file.pdf", save_path)

        with open(save_path, "rb") as f:
            assert f.read() == mock_resp.content

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404 Not Found")

        with patch("pdfviewer.requests.get", return_value=mock_resp):
            with pytest.raises(Exception, match="404 Not Found"):
                download_pdf("https://example.com/missing.pdf", "out.pdf")

    def test_raises_when_not_pdf_content(self, tmp_path):
        save_path = str(tmp_path / "test.pdf")
        mock_resp = self._make_response(content=b"hi", content_type="text/html")

        with patch("pdfviewer.requests.get", return_value=mock_resp):
            with pytest.raises(ValueError, match="PDF가 아닐"):
                download_pdf("https://example.com/file.html", save_path)

    def test_uses_correct_headers(self):
        mock_resp = self._make_response()

        with patch("pdfviewer.requests.get", return_value=mock_resp) as mock_get:
            try:
                download_pdf("https://example.com/file.pdf", "/tmp/f.pdf")
            except Exception:
                pass

            _, kwargs = mock_get.call_args
            assert "headers" in kwargs
            assert "User-Agent" in kwargs["headers"]


# ── extract_pdf_text ──────────────────────────────────────────────

class TestExtractPdfText:
    def _make_mock_pdf(self, pages_text, tables=None):
        """pdfplumber mock 생성"""
        mock_pages = []
        for i, text in enumerate(pages_text):
            mock_page = MagicMock()
            mock_page.extract_text.return_value = text
            mock_page.extract_tables.return_value = tables[i] if tables else []
            mock_pages.append(mock_page)

        mock_pdf = MagicMock()
        mock_pdf.pages = mock_pages
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        return mock_pdf

    def test_extracts_text_from_single_page(self):
        mock_pdf = self._make_mock_pdf(["페이지1 내용"])

        with patch("pdfviewer.pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("fake.pdf")

        assert len(result["pages"]) == 1
        assert result["pages"][0]["page"] == 1
        assert result["pages"][0]["text"] == "페이지1 내용"

    def test_extracts_text_from_multiple_pages(self):
        mock_pdf = self._make_mock_pdf(["1페이지", "2페이지", "3페이지"])

        with patch("pdfviewer.pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("fake.pdf")

        assert len(result["pages"]) == 3
        assert result["pages"][2]["page"] == 3
        assert result["pages"][2]["text"] == "3페이지"

    def test_handles_empty_page_text(self):
        mock_pdf = self._make_mock_pdf([None])  # extract_text가 None 반환

        with patch("pdfviewer.pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("fake.pdf")

        assert result["pages"][0]["text"] == ""

    def test_extracts_tables(self):
        table_data = [[["헤더1", "헤더2"], ["값1", "값2"]]]
        mock_pdf = self._make_mock_pdf(["텍스트"], tables=table_data)

        with patch("pdfviewer.pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("fake.pdf")

        assert len(result["tables"]) == 1
        assert result["tables"][0]["page"] == 1
        assert result["tables"][0]["data"] == table_data[0]

    def test_returns_empty_tables_when_none(self):
        mock_pdf = self._make_mock_pdf(["텍스트만"])

        with patch("pdfviewer.pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("fake.pdf")

        assert result["tables"] == []

    def test_result_structure(self):
        mock_pdf = self._make_mock_pdf(["내용"])

        with patch("pdfviewer.pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("fake.pdf")

        assert "pages" in result
        assert "tables" in result
