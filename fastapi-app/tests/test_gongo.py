"""
gongo.py 테스트

Playwright를 AsyncMock으로 대체해 실제 브라우저 없이 테스트합니다.
"""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

from gongo import crawl_sogang_jobs


def make_mock_page(html_content="<html><body></body></html>", url="https://job.sogang.ac.kr/"):
    """Playwright Page AsyncMock 생성"""
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value=html_content)
    mock_page.url = url
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.fill = AsyncMock()
    mock_page.press = AsyncMock()

    # locator("a:has-text('다음')") → count() == 0 → 마지막 페이지
    mock_locator = AsyncMock()
    mock_locator.count = AsyncMock(return_value=0)
    mock_page.locator = MagicMock(return_value=mock_locator)

    mock_page.on = MagicMock()
    return mock_page


def make_mock_browser(page):
    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=page)
    mock_browser.close = AsyncMock()
    return mock_browser


def make_mock_playwright(browser):
    mock_pw = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(return_value=browser)
    return mock_pw


def make_playwright_context(browser):
    """async with async_playwright() as p: 를 모킹"""
    mock_pw = make_mock_playwright(browser)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm


LIST_HTML_NO_JOBS = "<html><body><p>공고 없음</p></body></html>"

LIST_HTML_WITH_JOB = """
<html><body>
  <a href="javascript:detailView('abc123', '99')">백엔드 개발자 모집</a>
</body></html>
"""

DETAIL_HTML = """
<html><body>
  <span id="WorkType">정규직</span>
  <span id="Edate">2026-06-30</span>
  <span id="Duty">개발</span>
</body></html>
"""


@pytest.mark.asyncio
async def test_no_jobs_found_no_file_written(tmp_path):
    """공고 링크가 없으면 파일을 생성하지 않음"""
    page = make_mock_page(html_content=LIST_HTML_NO_JOBS)
    browser = make_mock_browser(page)
    ctx = make_playwright_context(browser)

    with patch("gongo.async_playwright", return_value=ctx):
        with patch("builtins.open", side_effect=AssertionError("파일이 열리면 안 됨")):
            await crawl_sogang_jobs()  # 파일 open이 호출되지 않아야 함


@pytest.mark.asyncio
async def test_jobs_found_file_written(tmp_path):
    """공고가 있으면 txt 파일에 저장"""
    # 목록 페이지: 공고 1개, 상세 페이지: 상세 정보
    call_count = {"n": 0}

    async def mock_content():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return LIST_HTML_WITH_JOB   # 목록 페이지
        return DETAIL_HTML              # 상세 페이지

    page = make_mock_page()
    page.content = mock_content
    page.url = "https://job.sogang.ac.kr/recruit/RecruitView.aspx?rcdx=abc123"

    browser = make_mock_browser(page)
    ctx = make_playwright_context(browser)

    written_content = []

    original_open = open

    def fake_open(path, mode="r", **kwargs):
        if "sogang_jobs_" in str(path) and "w" in mode:
            import io
            buf = io.StringIO()

            class FakeFile:
                def write(self, s): written_content.append(s)
                def __enter__(self): return self
                def __exit__(self, *a): pass

            return FakeFile()
        return original_open(path, mode, **kwargs)

    with patch("gongo.async_playwright", return_value=ctx), \
         patch("builtins.open", side_effect=fake_open):
        await crawl_sogang_jobs()

    combined = "".join(written_content)
    assert "백엔드 개발자 모집" in combined
    assert "정규직" in combined
    assert "2026-06-30" in combined


@pytest.mark.asyncio
async def test_individual_job_error_continues(tmp_path):
    """개별 공고 크롤링 오류가 발생해도 전체가 멈추지 않음"""
    call_count = {"n": 0}

    async def mock_content():
        call_count["n"] += 1
        if call_count["n"] == 1:
            # 공고 2개 포함
            return """
            <html><body>
              <a href="javascript:detailView('hash1', '1')">공고1</a>
              <a href="javascript:detailView('hash2', '2')">공고2</a>
            </body></html>
            """
        if call_count["n"] == 2:
            raise Exception("상세 페이지 오류")
        return DETAIL_HTML

    page = make_mock_page()
    page.content = mock_content
    page.url = "https://job.sogang.ac.kr/recruit/RecruitView.aspx"

    browser = make_mock_browser(page)
    ctx = make_playwright_context(browser)

    written = []

    def fake_open(path, mode="r", **kwargs):
        if "sogang_jobs_" in str(path) and "w" in mode:
            class FakeFile:
                def write(self, s): written.append(s)
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeFile()
        return open(path, mode, **kwargs)

    with patch("gongo.async_playwright", return_value=ctx), \
         patch("builtins.open", side_effect=fake_open):
        await crawl_sogang_jobs()  # 예외가 전파되지 않아야 함


@pytest.mark.asyncio
async def test_browser_closed_after_crawl():
    """크롤링 완료 후 브라우저가 반드시 close됨"""
    page = make_mock_page(html_content=LIST_HTML_NO_JOBS)
    browser = make_mock_browser(page)
    ctx = make_playwright_context(browser)

    with patch("gongo.async_playwright", return_value=ctx):
        await crawl_sogang_jobs()

    browser.close.assert_called_once()
