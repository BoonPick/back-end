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
