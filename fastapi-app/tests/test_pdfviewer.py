import sys
from unittest.mock import MagicMock

# pdfplumber (and its broken cffi/cryptography chain) is not available in this
# environment.  Stub it out before any source module is imported so that
# collection does not crash.
sys.modules.setdefault('pdfplumber', MagicMock())

import pytest
from pdfviewer import to_download_url, find_pdf_urls


class TestToDownloadUrl:
    def test_converts_viewer_url(self):
        url = "https://scc.sogang.ac.kr/viewer?pathStr%3Dsome%2Fpath%26fileName%3Dfile.pdf%26gubun=cmsfile"
        result = to_download_url(url)
        assert "Download3" in result
        assert "pathStr=" in result

    def test_returns_original_when_no_pathstr(self):
        url = "https://example.com/file.pdf"
        assert to_download_url(url) == url

    def test_includes_filename_when_present(self):
        url = "https://scc.sogang.ac.kr/v?pathStr%3Dabc%26fileName%3Dtest.pdf%26gubun=x"
        result = to_download_url(url)
        assert "fileName=test.pdf" in result
        assert "pathStr=abc" in result

    def test_handles_missing_filename(self):
        url = "https://scc.sogang.ac.kr/v?pathStr%3Dabc%26gubun=x"
        result = to_download_url(url)
        assert "pathStr=abc" in result


class TestFindPdfUrls:
    def test_finds_pdf_in_anchor_tag(self):
        html = '<a href="/files/notice.pdf">다운로드</a>'
        result = find_pdf_urls(html, {})
        assert any("notice.pdf" in u for u in result)

    def test_finds_pdf_in_iframe(self):
        html = '<iframe src="/viewer/doc.pdf"></iframe>'
        result = find_pdf_urls(html, {})
        assert any("doc.pdf" in u for u in result)

    def test_finds_pdf_in_api_filelist(self):
        html = ""
        api_data = {"fileList": [{"url": "/files/attach.pdf"}]}
        result = find_pdf_urls(html, api_data)
        assert any("attach.pdf" in u for u in result)

    def test_deduplicates_urls(self):
        html = '<a href="/files/dup.pdf">1</a><a href="/files/dup.pdf">2</a>'
        result = find_pdf_urls(html, {})
        assert len(result) == 1

    def test_converts_relative_to_absolute(self):
        html = '<a href="/files/notice.pdf">다운로드</a>'
        result = find_pdf_urls(html, {})
        assert all(u.startswith("http") for u in result)

    def test_ignores_non_pdf_links(self):
        html = '<a href="/page/index.html">홈</a>'
        result = find_pdf_urls(html, {})
        assert result == []

    def test_empty_input(self):
        assert find_pdf_urls("", {}) == []


# ── auto-generated: download_pdf ──
import requests
from unittest.mock import MagicMock, patch, mock_open
from pdfviewer import download_pdf


class TestDownloadPdf:
    def _make_response(self, status_code=200, content=b"%PDF-" + b"x" * 200,
                       content_type="application/pdf", raise_for_status=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.content = content
        resp.headers = {"Content-Type": content_type}
        if raise_for_status:
            resp.raise_for_status.side_effect = raise_for_status
        else:
            resp.raise_for_status.return_value = None
        return resp

    def test_downloads_and_writes_pdf(self, tmp_path):
        pdf_content = b"%PDF-" + b"A" * 200
        resp = self._make_response(content=pdf_content)
        save_path = str(tmp_path / "test.pdf")

        with patch("requests.get", return_value=resp):
            with patch("builtins.open", mock_open()) as m_open:
                download_pdf("http://example.com/file.pdf", save_path)

        m_open.assert_called_once_with(save_path, "wb")
        handle = m_open()
        handle.write.assert_called_once_with(pdf_content)

    def test_raises_on_http_error(self):
        resp = self._make_response(
            raise_for_status=requests.exceptions.HTTPError("404")
        )
        with patch("requests.get", return_value=resp):
            with pytest.raises(requests.exceptions.HTTPError):
                download_pdf("http://example.com/missing.pdf", "/tmp/x.pdf")

    def test_raises_value_error_when_not_pdf_and_small_content(self):
        resp = self._make_response(content=b"<html>small</html>",
                                   content_type="text/html")
        with patch("requests.get", return_value=resp):
            with pytest.raises(ValueError, match="PDF"):
                download_pdf("http://example.com/notpdf", "/tmp/x.pdf")

    def test_no_error_when_content_type_not_pdf_but_content_large(self):
        large_content = b"x" * 200
        resp = self._make_response(content=large_content, content_type="application/octet-stream")
        with patch("requests.get", return_value=resp):
            with patch("builtins.open", mock_open()):
                # Should not raise — content >= 100 bytes even if content-type is wrong
                download_pdf("http://example.com/file.bin", "/tmp/x.pdf")

    def test_no_error_when_content_type_is_pdf_and_content_small(self):
        small_content = b"x" * 10
        resp = self._make_response(content=small_content, content_type="application/pdf")
        with patch("requests.get", return_value=resp):
            with patch("builtins.open", mock_open()):
                # Should not raise — content-type contains "pdf"
                download_pdf("http://example.com/file.pdf", "/tmp/x.pdf")

    def test_requests_get_called_with_correct_url(self):
        resp = self._make_response()
        with patch("requests.get", return_value=resp) as mock_get:
            with patch("builtins.open", mock_open()):
                download_pdf("http://example.com/doc.pdf", "/tmp/doc.pdf")

        call_args = mock_get.call_args
        assert call_args[0][0] == "http://example.com/doc.pdf"


# ── auto-generated: extract_pdf_text ──
from pdfviewer import extract_pdf_text


class TestExtractPdfText:
    def _make_mock_pdf(self, pages_data):
        """pages_data: list of (text, tables) tuples."""
        mock_pages = []
        for text, tables in pages_data:
            page = MagicMock()
            page.extract_text.return_value = text
            page.extract_tables.return_value = tables
            mock_pages.append(page)

        mock_pdf = MagicMock()
        mock_pdf.pages = mock_pages
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        return mock_pdf

    def test_extracts_text_per_page(self):
        mock_pdf = self._make_mock_pdf([("Page one text", []), ("Page two text", [])])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("/fake/path.pdf")

        assert len(result["pages"]) == 2
        assert result["pages"][0]["text"] == "Page one text"
        assert result["pages"][0]["page"] == 1
        assert result["pages"][1]["text"] == "Page two text"
        assert result["pages"][1]["page"] == 2

    def test_extracts_tables(self):
        table_data = [["col1", "col2"], ["val1", "val2"]]
        mock_pdf = self._make_mock_pdf([("text", [table_data])])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("/fake/path.pdf")

        assert len(result["tables"]) == 1
        assert result["tables"][0]["page"] == 1
        assert result["tables"][0]["table_index"] == 0
        assert result["tables"][0]["data"] == table_data

    def test_returns_empty_text_when_page_has_none(self):
        mock_pdf = self._make_mock_pdf([(None, [])])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("/fake/path.pdf")

        assert result["pages"][0]["text"] == ""

    def test_multiple_tables_per_page(self):
        table1 = [["a", "b"]]
        table2 = [["c", "d"]]
        mock_pdf = self._make_mock_pdf([("text", [table1, table2])])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("/fake/path.pdf")

        assert len(result["tables"]) == 2
        assert result["tables"][0]["table_index"] == 0
        assert result["tables"][1]["table_index"] == 1

    def test_result_has_pages_and_tables_keys(self):
        mock_pdf = self._make_mock_pdf([])
        with patch("pdfplumber.open", return_value=mock_pdf):
            result = extract_pdf_text("/fake/path.pdf")

        assert "pages" in result
        assert "tables" in result

    def test_opens_pdf_at_given_path(self):
        mock_pdf = self._make_mock_pdf([("text", [])])
        with patch("pdfplumber.open", return_value=mock_pdf) as mock_open_pdf:
            extract_pdf_text("/some/path/doc.pdf")

        mock_open_pdf.assert_called_once_with("/some/path/doc.pdf")


# ── auto-generated: find_pdf_urls (relative→absolute path conversion) ──
class TestFindPdfUrlsRelativeToAbsolute:
    def test_relative_path_starting_with_slash_gets_base_url(self):
        html = '<a href="/notice/file.pdf">link</a>'
        result = find_pdf_urls(html, {})
        assert any(u.startswith("https://www.sogang.ac.kr/notice/") for u in result)

    def test_relative_path_without_slash_gets_base_url_with_separator(self):
        # Paths not starting with "/" or "http" should have BASE_URL + "/" prepended
        html = '<a href="relative/path/file.pdf">link</a>'
        result = find_pdf_urls(html, {})
        assert any("sogang.ac.kr" in u and "relative/path/file.pdf" in u for u in result)

    def test_absolute_http_url_unchanged_by_base_url_prepend(self):
        html = '<a href="https://external.com/doc.pdf">link</a>'
        result = find_pdf_urls(html, {})
        # The URL should remain http-based (not double-prepended)
        assert any(u.startswith("https://external.com") or "external.com" in u for u in result)

    def test_slash_relative_does_not_add_extra_slash(self):
        html = '<a href="/files/doc.pdf">link</a>'
        result = find_pdf_urls(html, {})
        # Should be BASE_URL + "/files/doc.pdf" = "https://www.sogang.ac.kr/files/doc.pdf"
        # Not "https://www.sogang.ac.kr//files/doc.pdf"
        assert not any("sogang.ac.kr//" in u for u in result)
