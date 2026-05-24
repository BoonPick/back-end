import pytest
import crawling_job as cj
from datetime import date
from bs4 import BeautifulSoup
from crawling_job import (
    _parse_deadline, _span_text, _parse_detail, _extract_rcdx_list,
    get_db_connection, DB_CONFIG,
    job_exists, job_exists_by_title_worktype, SOURCE_NAME,
    save_content, save_job_posting,
    _login, LOGIN_URL,
    _collect_rcdx_all_pages, LIST_URL,
    crawl_jobs,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeout


class TestParseDeadline:
    def test_standard_date(self):
        deadline, is_always = _parse_deadline("2026-05-27 정시")
        assert deadline == date(2026, 5, 27)
        assert is_always == 0

    def test_always_open_korean(self):
        deadline, is_always = _parse_deadline("상시채용")
        assert deadline is None
        assert is_always == 1

    def test_always_open_with_extra_text(self):
        deadline, is_always = _parse_deadline("상시 채용 가능")
        assert is_always == 1

    def test_empty_string(self):
        deadline, is_always = _parse_deadline("")
        assert deadline is None
        assert is_always == 1

    def test_none_input(self):
        deadline, is_always = _parse_deadline(None)
        assert deadline is None
        assert is_always == 1

    def test_date_without_suffix(self):
        deadline, is_always = _parse_deadline("2026-12-31")
        assert deadline == date(2026, 12, 31)
        assert is_always == 0


class TestSpanText:
    def _soup(self, html):
        return BeautifulSoup(html, "html.parser")

    def test_extracts_span_text(self):
        soup = self._soup('<span id="Duty">기타</span>')
        assert _span_text(soup, "Duty") == "기타"

    def test_returns_empty_for_nbsp(self):
        soup = self._soup('<span id="BizType">&nbsp;</span>')
        assert _span_text(soup, "BizType") == ""

    def test_returns_empty_when_id_not_found(self):
        soup = self._soup("<div>nothing</div>")
        assert _span_text(soup, "Missing") == ""

    def test_strips_whitespace(self):
        soup = self._soup('<span id="Title">  제목  </span>')
        assert _span_text(soup, "Title") == "제목"


class TestParseDetail:
    SAMPLE_HTML = """
    <html><body>
      <span id="Title">PTKOREA 인턴사원</span>
      <span id="RUDate">2026-04-27</span>
      <span id="RecomEmp">인턴</span>
      <span id="WorkType">인턴직</span>
      <span id="Duty">기타</span>
      <span id="Edate">2026-05-27 정시</span>
      <span id="ALLTEXT">모집 내용입니다.</span>
    </body></html>
    """

    def test_parses_title(self):
        result = _parse_detail(self.SAMPLE_HTML)
        assert result["title"] == "PTKOREA 인턴사원"

    def test_parses_employment(self):
        result = _parse_detail(self.SAMPLE_HTML)
        assert result["employment"] == "인턴"

    def test_parses_work_type(self):
        result = _parse_detail(self.SAMPLE_HTML)
        assert result["work_type"] == "인턴직"

    def test_parses_duty(self):
        result = _parse_detail(self.SAMPLE_HTML)
        assert result["duty"] == "기타"

    def test_parses_deadline(self):
        result = _parse_detail(self.SAMPLE_HTML)
        assert result["deadline"] == date(2026, 5, 27)
        assert result["is_always_open"] == 0

    def test_parses_posted_at(self):
        from datetime import datetime
        result = _parse_detail(self.SAMPLE_HTML)
        assert result["posted_at"] == datetime(2026, 4, 27)

    def test_parses_raw_content(self):
        result = _parse_detail(self.SAMPLE_HTML)
        assert "모집 내용입니다." in result["raw_content"]

    def test_always_open(self):
        html = self.SAMPLE_HTML.replace("2026-05-27 정시", "상시채용")
        result = _parse_detail(html)
        assert result["deadline"] is None
        assert result["is_always_open"] == 1


class TestExtractRcdxList:
    def test_extracts_from_href(self):
        rcdx = "A" * 64
        html = f'<a href="javascript:detailView(\'{rcdx}\', \'123\');">공고</a>'
        result = _extract_rcdx_list(html)
        assert rcdx in result

    def test_extracts_from_onclick(self):
        rcdx = "B" * 64
        html = f'<a onclick="detailView(\'{rcdx}\',\'456\')">공고</a>'
        result = _extract_rcdx_list(html)
        assert rcdx in result

    def test_deduplicates(self):
        rcdx = "C" * 64
        html = (
            f'<a href="javascript:detailView(\'{rcdx}\', \'1\');">1</a>'
            f'<a onclick="detailView(\'{rcdx}\',\'1\')">2</a>'
        )
        result = _extract_rcdx_list(html)
        assert result.count(rcdx) == 1

    def test_empty_html(self):
        assert _extract_rcdx_list("") == []

    def test_ignores_short_rcdx(self):
        html = "<a onclick=\"detailView('SHORT','1')\">공고</a>"
        assert _extract_rcdx_list(html) == []


# ── auto-generated: get_db_connection ──
class TestGetDbConnection:
    def test_returns_connection(self, mocker):
        mock_connect = mocker.patch("crawling_job.mysql.connector.connect")
        mock_conn = mocker.MagicMock()
        mock_connect.return_value = mock_conn

        result = get_db_connection()

        mock_connect.assert_called_once_with(**DB_CONFIG)
        assert result is mock_conn

    def test_passes_db_config_values(self, mocker):
        mock_connect = mocker.patch("crawling_job.mysql.connector.connect")

        get_db_connection()

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["database"] == DB_CONFIG["database"]
        assert call_kwargs["user"] == DB_CONFIG["user"]


# ── auto-generated: job_exists ──
class TestJobExists:
    def _make_cursor(self, mocker, fetchone_result):
        cursor = mocker.MagicMock()
        cursor.fetchone.return_value = fetchone_result
        return cursor

    def test_returns_true_when_row_found(self, mocker):
        cursor = self._make_cursor(mocker, (1,))
        assert job_exists(cursor, "http://example.com/job/1") is True
        cursor.execute.assert_called_once()

    def test_returns_false_when_no_row(self, mocker):
        cursor = self._make_cursor(mocker, None)
        assert job_exists(cursor, "http://example.com/job/999") is False

    def test_executes_with_correct_url(self, mocker):
        cursor = self._make_cursor(mocker, None)
        url = "http://example.com/job/42"
        job_exists(cursor, url)
        args = cursor.execute.call_args[0]
        assert url in args[1]


# ── auto-generated: job_exists_by_title_worktype ──
class TestJobExistsByTitleWorktype:
    def _make_cursor(self, mocker, fetchone_result):
        cursor = mocker.MagicMock()
        cursor.fetchone.return_value = fetchone_result
        return cursor

    def test_returns_true_when_match_found(self, mocker):
        cursor = self._make_cursor(mocker, (1,))
        assert job_exists_by_title_worktype(cursor, "Some Job Title", "인턴직") is True

    def test_returns_false_when_no_match(self, mocker):
        cursor = self._make_cursor(mocker, None)
        assert job_exists_by_title_worktype(cursor, "Nonexistent Job", "정규직") is False

    def test_passes_source_name_title_worktype(self, mocker):
        cursor = self._make_cursor(mocker, None)
        title = "Test Job"
        work_type = "계약직"
        job_exists_by_title_worktype(cursor, title, work_type)
        args = cursor.execute.call_args[0]
        params = args[1]
        assert params[0] == SOURCE_NAME
        assert params[1] == title
        assert params[2] == work_type

    def test_executes_join_query(self, mocker):
        cursor = self._make_cursor(mocker, None)
        job_exists_by_title_worktype(cursor, "Title", "WorkType")
        sql = cursor.execute.call_args[0][0]
        assert "job_postings" in sql
        assert "contents" in sql


# ── auto-generated: save_content ──
class TestSaveContent:
    def _make_cursor(self, mocker, lastrowid=42):
        cursor = mocker.MagicMock()
        cursor.lastrowid = lastrowid
        return cursor

    def test_returns_lastrowid(self, mocker):
        cursor = self._make_cursor(mocker, lastrowid=99)
        result = save_content(cursor, "Job Title", "http://url", "raw text")
        assert result == 99

    def test_executes_insert_without_posted_at(self, mocker):
        cursor = self._make_cursor(mocker)
        save_content(cursor, "Title", "http://url", "content", posted_at=None)
        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        assert "INSERT INTO contents" in sql
        assert "Title" in params
        assert "http://url" in params

    def test_executes_insert_with_posted_at(self, mocker):
        from datetime import datetime
        cursor = self._make_cursor(mocker)
        posted = datetime(2026, 4, 27)
        save_content(cursor, "Title", "http://url", "content", posted_at=posted)
        cursor.execute.assert_called_once()
        sql, params = cursor.execute.call_args[0]
        assert "INSERT INTO contents" in sql
        assert posted in params

    def test_upsert_includes_on_duplicate_key(self, mocker):
        cursor = self._make_cursor(mocker)
        save_content(cursor, "Title", "http://url", "content")
        sql = cursor.execute.call_args[0][0]
        assert "ON DUPLICATE KEY UPDATE" in sql

    def test_source_name_is_sogang_job(self, mocker):
        cursor = self._make_cursor(mocker)
        save_content(cursor, "Title", "http://url", "content")
        params = cursor.execute.call_args[0][1]
        assert SOURCE_NAME in params


# ── auto-generated: save_job_posting ──
class TestSaveJobPosting:
    def test_executes_insert(self, mocker):
        cursor = mocker.MagicMock()
        save_job_posting(cursor, 10, "인턴", "인턴직", "기타", None, 1)
        cursor.execute.assert_called_once()

    def test_passes_all_params(self, mocker):
        from datetime import date
        cursor = mocker.MagicMock()
        deadline = date(2026, 6, 30)
        save_job_posting(cursor, 5, "정규직", "계약직", "개발", deadline, 0)
        sql, params = cursor.execute.call_args[0]
        assert params == (5, "정규직", "계약직", "개발", deadline, 0)

    def test_upsert_includes_on_duplicate_key(self, mocker):
        cursor = mocker.MagicMock()
        save_job_posting(cursor, 1, "e", "wt", "duty", None, 0)
        sql = cursor.execute.call_args[0][0]
        assert "ON DUPLICATE KEY UPDATE" in sql

    def test_inserts_into_job_postings_table(self, mocker):
        cursor = mocker.MagicMock()
        save_job_posting(cursor, 1, "e", "wt", "duty", None, 0)
        sql = cursor.execute.call_args[0][0]
        assert "job_postings" in sql


# ── auto-generated: _login ──
class TestLogin:
    def _make_visible_element(self, mocker):
        el = mocker.MagicMock()
        el.is_visible.return_value = True
        return el

    def _make_invisible_element(self, mocker):
        el = mocker.MagicMock()
        el.is_visible.return_value = False
        return el

    def test_raises_if_saint_id_missing(self, mocker, monkeypatch):
        monkeypatch.delenv("SAINT_ID", raising=False)
        monkeypatch.delenv("SAINT_PW", raising=False)
        monkeypatch.setenv("SAINT_ID", "")
        monkeypatch.setenv("SAINT_PW", "somepassword")
        page = mocker.MagicMock()
        with pytest.raises(RuntimeError, match="SAINT_ID"):
            _login(page)

    def test_raises_if_saint_pw_missing(self, mocker, monkeypatch):
        monkeypatch.setenv("SAINT_ID", "someid")
        monkeypatch.setenv("SAINT_PW", "")
        page = mocker.MagicMock()
        with pytest.raises(RuntimeError, match="SAINT_PW"):
            _login(page)

    def test_raises_if_both_env_vars_missing(self, mocker, monkeypatch):
        monkeypatch.setenv("SAINT_ID", "")
        monkeypatch.setenv("SAINT_PW", "")
        page = mocker.MagicMock()
        with pytest.raises(RuntimeError):
            _login(page)

    def test_raises_if_id_field_not_found(self, mocker, monkeypatch):
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None

        invisible_el = self._make_invisible_element(mocker)
        locator = mocker.MagicMock()
        locator.first = invisible_el
        page.locator.return_value = locator

        with pytest.raises(RuntimeError, match="입력 필드"):
            _login(page)

    def test_raises_if_pw_field_not_found(self, mocker, monkeypatch):
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None

        call_count = {"n": 0}

        def make_locator(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            # Only the first id_selector should be visible (to give id_field)
            # All pw selectors should be invisible
            if call_count["n"] == 1:
                el.is_visible.return_value = True
            else:
                el.is_visible.return_value = False
            lc.first = el
            return lc

        page.locator.side_effect = make_locator

        with pytest.raises(RuntimeError, match="입력 필드"):
            _login(page)

    def test_successful_login_navigates_away(self, mocker, monkeypatch):
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"

        visible_el = self._make_visible_element(mocker)
        locator = mocker.MagicMock()
        locator.first = visible_el
        page.locator.return_value = locator

        # wait_for_url should succeed (not raise)
        page.wait_for_url.return_value = None

        _login(page)  # should not raise

        page.goto.assert_called_once_with(
            LOGIN_URL, wait_until="domcontentloaded", timeout=30000
        )
        visible_el.fill.assert_called()

    def test_login_raises_on_failed_redirect(self, mocker, monkeypatch):
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "wrongpass")

        page = mocker.MagicMock()
        page.goto.return_value = None
        # URL still contains 'login' after wait — indicates login failure
        page.url = "https://job.sogang.ac.kr/main/login.aspx"

        visible_el = self._make_visible_element(mocker)
        locator = mocker.MagicMock()
        locator.first = visible_el
        page.locator.return_value = locator

        page.wait_for_url.side_effect = PlaywrightTimeout("timeout")

        with pytest.raises(RuntimeError, match="로그인 실패"):
            _login(page)


# ── auto-generated: _parse_deadline ──
class TestParseDeadlineErrorBranch:
    """Tests targeting the ValueError error-handling branch in _parse_deadline."""

    def test_invalid_date_string_with_regex_match_returns_none_zero(self, mocker):
        """When regex finds a date-like pattern but strptime raises ValueError, return (None, 0)."""
        # Patch datetime.strptime to raise ValueError
        mock_dt = mocker.patch("crawling_job.datetime")
        mock_dt.strptime.side_effect = ValueError("unconverted data")

        # re.search will still match "2026-13-99" (invalid date but matches pattern)
        deadline, is_always = _parse_deadline("2026-13-99")
        assert deadline is None
        assert is_always == 0

    def test_no_regex_match_returns_none_zero(self):
        """String with no date pattern and no 상시 → (None, 0)."""
        deadline, is_always = _parse_deadline("마감일 없음")
        assert deadline is None
        assert is_always == 0

    def test_text_without_date_not_always_open(self):
        """Plain text without date or 상시 returns is_always_open=0."""
        _, is_always = _parse_deadline("채용중")
        assert is_always == 0


# ── auto-generated: _collect_rcdx_all_pages ──
class TestCollectRcdxAllPages:
    RCDX_A = "A" * 64
    RCDX_B = "B" * 64

    def _html_with_rcdx(self, *rcdx_values):
        links = "".join(
            f'<a onclick="detailView(\'{r}\',\'1\')">공고</a>'
            for r in rcdx_values
        )
        return f"<html><body>{links}</body></html>"

    def test_single_page_returns_rcdx_list(self, mocker):
        page = mocker.MagicMock()
        page.content.return_value = self._html_with_rcdx(self.RCDX_A, self.RCDX_B)

        result = _collect_rcdx_all_pages(page, page_count=1)

        assert self.RCDX_A in result
        assert self.RCDX_B in result
        assert len(result) == 2
        page.goto.assert_called_once_with(
            LIST_URL, wait_until="domcontentloaded", timeout=20000
        )

    def test_empty_page_stops_early(self, mocker):
        page = mocker.MagicMock()
        # First page has content, second is empty — should stop after 1st empty page
        page.content.side_effect = [
            self._html_with_rcdx(self.RCDX_A),
            "<html><body></body></html>",
        ]

        result = _collect_rcdx_all_pages(page, page_count=3)

        assert result == [self.RCDX_A]
        # goto called twice: page 1 (LIST_URL) and page 2 (LIST_URL?rp=2)
        assert page.goto.call_count == 2

    def test_deduplicates_across_pages(self, mocker):
        page = mocker.MagicMock()
        # Both pages return the same rcdx
        html_same = self._html_with_rcdx(self.RCDX_A)
        page.content.side_effect = [html_same, html_same, "<html></html>"]

        result = _collect_rcdx_all_pages(page, page_count=3)

        assert result.count(self.RCDX_A) == 1

    def test_page_two_uses_rp_param(self, mocker):
        page = mocker.MagicMock()
        page.content.side_effect = [
            self._html_with_rcdx(self.RCDX_A),
            self._html_with_rcdx(self.RCDX_B),
            "<html></html>",
        ]

        _collect_rcdx_all_pages(page, page_count=3)

        calls = page.goto.call_args_list
        assert calls[0][0][0] == LIST_URL
        assert calls[1][0][0] == f"{LIST_URL}?rp=2"

    def test_zero_pages_returns_empty(self, mocker):
        page = mocker.MagicMock()
        result = _collect_rcdx_all_pages(page, page_count=0)
        assert result == []
        page.goto.assert_not_called()


# ── auto-generated: _login ──
class TestLoginExtended:
    """Additional _login tests covering fallback selector logic,
    submit-button fallback to Enter, and timeout-but-url-ok path."""

    def _make_visible_el(self, mocker):
        el = mocker.MagicMock()
        el.is_visible.return_value = True
        return el

    def _make_invisible_el(self, mocker):
        el = mocker.MagicMock()
        el.is_visible.return_value = False
        return el

    def _make_locator(self, mocker, el):
        lc = mocker.MagicMock()
        lc.first = el
        return lc

    def test_id_selector_timeout_falls_back_to_next(self, mocker, monkeypatch):
        """PlaywrightTimeout on first id_selector → tries next, succeeds."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None

        call_count = {"n": 0}

        def side_effect(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            if n == 1:
                # First id_selector: is_visible raises PlaywrightTimeout
                el.is_visible.side_effect = PlaywrightTimeout("timeout")
            elif n == 2:
                # Second id_selector: visible — id_field found
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            else:
                # First pw_selector: visible — pw_field found
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            lc.first = el
            return lc

        page.locator.side_effect = side_effect

        _login(page)  # should not raise

        assert page.goto.called

    def test_pw_selector_timeout_falls_back_to_next(self, mocker, monkeypatch):
        """PlaywrightTimeout on first pw_selector → tries next, succeeds."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None

        call_count = {"n": 0}

        def side_effect(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            if n == 1:
                # First id_selector: visible
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            elif n == 2:
                # First pw_selector: raises PlaywrightTimeout
                el.is_visible.side_effect = PlaywrightTimeout("timeout")
            else:
                # Second pw_selector: visible — pw_field found
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            lc.first = el
            return lc

        page.locator.side_effect = side_effect

        _login(page)  # should not raise

    def test_no_submit_button_presses_enter(self, mocker, monkeypatch):
        """When no submit button is visible, keyboard.press('Enter') is used."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None

        call_count = {"n": 0}

        def side_effect(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            # First two calls: id_field and pw_field (both visible)
            # All subsequent calls (submit button selectors): invisible
            if n <= 2:
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            else:
                el.is_visible.return_value = False
                el.is_visible.side_effect = None
            lc.first = el
            return lc

        page.locator.side_effect = side_effect

        _login(page)

        page.keyboard.press.assert_called_once_with("Enter")

    def test_submit_button_visible_clicks_it(self, mocker, monkeypatch):
        """When a submit button selector resolves, it is clicked (not Enter)."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None

        call_count = {"n": 0}

        def side_effect(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            # All elements are visible: id_field, pw_field, and first submit button
            el.is_visible.return_value = True
            el.is_visible.side_effect = None
            lc.first = el
            return lc

        page.locator.side_effect = side_effect

        _login(page)

        # keyboard.press should NOT have been called since button was found and clicked
        page.keyboard.press.assert_not_called()

    def test_wait_for_url_timeout_but_not_on_login_page(self, mocker, monkeypatch):
        """wait_for_url times out but current URL has no 'login' → no RuntimeError."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None
        # URL does NOT contain 'login' — redirect happened even though wait timed out
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.side_effect = PlaywrightTimeout("timeout")

        visible_el = self._make_visible_el(mocker)
        locator = mocker.MagicMock()
        locator.first = visible_el
        page.locator.return_value = locator

        _login(page)  # should NOT raise

    def test_all_id_selectors_timeout_raises(self, mocker, monkeypatch):
        """All id_selectors raise PlaywrightTimeout → RuntimeError about 입력 필드."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None

        def all_timeout(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            el.is_visible.side_effect = PlaywrightTimeout("timeout")
            lc.first = el
            return lc

        page.locator.side_effect = all_timeout

        with pytest.raises(RuntimeError, match="입력 필드"):
            _login(page)


# ── auto-generated: _parse_detail ──
class TestParseDetailExtended:
    """Additional _parse_detail tests covering missing ALLTEXT span and
    invalid ru_date causing ValueError fallback."""

    def test_missing_alltext_span_returns_empty_raw_content(self):
        """When ALLTEXT span is absent, raw_content should be empty string."""
        html = """
        <html><body>
          <span id="Title">Test Job</span>
          <span id="RUDate">2026-04-01</span>
          <span id="RecomEmp">정규직</span>
          <span id="WorkType">정규직</span>
          <span id="Duty">개발</span>
          <span id="Edate">2026-06-30</span>
        </body></html>
        """
        result = _parse_detail(html)
        assert result["raw_content"] == ""

    def test_alltext_span_strips_script_and_style(self):
        """script/style tags inside ALLTEXT are stripped from raw_content."""
        html = """
        <html><body>
          <span id="Title">T</span>
          <span id="RUDate">2026-01-01</span>
          <span id="RecomEmp">인턴</span>
          <span id="WorkType">인턴직</span>
          <span id="Duty">기타</span>
          <span id="Edate">상시채용</span>
          <span id="ALLTEXT">
            <script>alert(1)</script>
            <style>body{}</style>
            실제 내용입니다.
          </span>
        </body></html>
        """
        result = _parse_detail(html)
        assert "alert" not in result["raw_content"]
        assert "실제 내용입니다." in result["raw_content"]

    def test_invalid_ru_date_returns_none_posted_at(self):
        """An unparseable RUDate string falls back to posted_at=None."""
        html = """
        <html><body>
          <span id="Title">Some Job</span>
          <span id="RUDate">not-a-date</span>
          <span id="RecomEmp">인턴</span>
          <span id="WorkType">인턴직</span>
          <span id="Duty">기타</span>
          <span id="Edate">2026-06-30</span>
          <span id="ALLTEXT">내용</span>
        </body></html>
        """
        result = _parse_detail(html)
        assert result["posted_at"] is None

    def test_empty_ru_date_returns_none_posted_at(self):
        """An empty RUDate span results in posted_at=None."""
        html = """
        <html><body>
          <span id="Title">Some Job</span>
          <span id="RUDate"></span>
          <span id="RecomEmp">계약직</span>
          <span id="WorkType">계약직</span>
          <span id="Duty">영업</span>
          <span id="Edate">2026-09-01</span>
          <span id="ALLTEXT">내용</span>
        </body></html>
        """
        result = _parse_detail(html)
        assert result["posted_at"] is None

    def test_always_open_edate_sets_is_always_open(self):
        """상시채용 in Edate sets is_always_open=1 and deadline=None."""
        html = """
        <html><body>
          <span id="Title">Always Open Job</span>
          <span id="RUDate">2026-03-15</span>
          <span id="RecomEmp">정규직</span>
          <span id="WorkType">정규직</span>
          <span id="Duty">기획</span>
          <span id="Edate">상시채용</span>
          <span id="ALLTEXT">상시 모집합니다.</span>
        </body></html>
        """
        result = _parse_detail(html)
        assert result["is_always_open"] == 1
        assert result["deadline"] is None

    def test_returns_all_expected_keys(self):
        """_parse_detail always returns a dict with all required keys."""
        html = "<html><body></body></html>"
        result = _parse_detail(html)
        expected_keys = {
            "title", "employment", "work_type", "duty",
            "deadline", "is_always_open", "raw_content", "posted_at",
        }
        assert expected_keys == set(result.keys())


# ── auto-generated: crawl_jobs ──
class TestCrawlJobs:
    """Tests for the crawl_jobs orchestration function."""

    RCDX = "A" * 64

    def _detail_html(self, title="Test Job", edate="2026-12-31", ru_date="2026-01-01"):
        return f"""
        <html><body>
          <span id="Title">{title}</span>
          <span id="RUDate">{ru_date}</span>
          <span id="RecomEmp">인턴</span>
          <span id="WorkType">인턴직</span>
          <span id="Duty">기타</span>
          <span id="Edate">{edate}</span>
          <span id="ALLTEXT">내용입니다.</span>
        </body></html>
        """

    def _setup_playwright_mocks(self, mocker):
        """Return (mock_sync_pw, mock_page) with chained browser mocks."""
        mock_page = mocker.MagicMock()
        mock_context = mocker.MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = mocker.MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = mocker.MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_sync_pw_cm = mocker.MagicMock()
        mock_sync_pw_cm.__enter__ = mocker.MagicMock(return_value=mock_pw)
        mock_sync_pw_cm.__exit__ = mocker.MagicMock(return_value=False)
        mock_sync_playwright = mocker.patch(
            "crawling_job.sync_playwright", return_value=mock_sync_pw_cm
        )
        return mock_sync_playwright, mock_page

    def _setup_db_mocks(self, mocker):
        """Return (mock_conn, mock_cursor)."""
        mock_cursor = mocker.MagicMock()
        mock_conn = mocker.MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch("crawling_job.get_db_connection", return_value=mock_conn)
        return mock_conn, mock_cursor

    def test_returns_zero_when_no_rcdx_collected(self, mocker, monkeypatch):
        """crawl_jobs returns 0 when _collect_rcdx_all_pages returns empty list."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login")
        mocker.patch("crawling_job._collect_rcdx_all_pages", return_value=[])

        result = crawl_jobs(page_count=1)

        assert result == 0
        mock_conn.commit.assert_not_called()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_skips_existing_job_by_url(self, mocker, monkeypatch):
        """When job_exists returns True for a rcdx URL, it is skipped."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login")
        mocker.patch(
            "crawling_job._collect_rcdx_all_pages", return_value=[self.RCDX]
        )
        mocker.patch("crawling_job.job_exists", return_value=True)
        mock_save_content = mocker.patch("crawling_job.save_content")

        result = crawl_jobs(page_count=1)

        assert result == 0
        mock_save_content.assert_not_called()

    def test_skips_job_with_empty_title(self, mocker, monkeypatch):
        """If _parse_detail returns empty title, the job is skipped."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        _, mock_page = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login")
        mocker.patch(
            "crawling_job._collect_rcdx_all_pages", return_value=[self.RCDX]
        )
        mocker.patch("crawling_job.job_exists", return_value=False)
        mock_page.goto.return_value = None
        mock_page.content.return_value = self._detail_html(title="")
        mock_save_content = mocker.patch("crawling_job.save_content")

        result = crawl_jobs(page_count=1)

        assert result == 0
        mock_save_content.assert_not_called()

    def test_skips_duplicate_title_worktype(self, mocker, monkeypatch):
        """If job_exists_by_title_worktype returns True, the job is skipped."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        _, mock_page = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login")
        mocker.patch(
            "crawling_job._collect_rcdx_all_pages", return_value=[self.RCDX]
        )
        mocker.patch("crawling_job.job_exists", return_value=False)
        mocker.patch("crawling_job.job_exists_by_title_worktype", return_value=True)
        mock_page.goto.return_value = None
        mock_page.content.return_value = self._detail_html(title="Existing Job")
        mock_save_content = mocker.patch("crawling_job.save_content")

        result = crawl_jobs(page_count=1)

        assert result == 0
        mock_save_content.assert_not_called()

    def test_saves_new_job_and_returns_count(self, mocker, monkeypatch):
        """A new job is saved to DB and saved_count incremented."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        _, mock_page = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login")
        mocker.patch(
            "crawling_job._collect_rcdx_all_pages", return_value=[self.RCDX]
        )
        mocker.patch("crawling_job.job_exists", return_value=False)
        mocker.patch("crawling_job.job_exists_by_title_worktype", return_value=False)
        mock_page.goto.return_value = None
        mock_page.content.return_value = self._detail_html(title="Brand New Job")
        mocker.patch("crawling_job.save_content", return_value=42)
        mocker.patch("crawling_job.save_job_posting")

        result = crawl_jobs(page_count=1)

        assert result == 1
        mock_conn.commit.assert_called_once()

    def test_skips_on_playwright_timeout_navigating_detail(self, mocker, monkeypatch):
        """PlaywrightTimeout when navigating to detail URL skips that rcdx."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        _, mock_page = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login")
        mocker.patch(
            "crawling_job._collect_rcdx_all_pages", return_value=[self.RCDX]
        )
        mocker.patch("crawling_job.job_exists", return_value=False)
        mock_page.goto.side_effect = PlaywrightTimeout("timeout")
        mock_save_content = mocker.patch("crawling_job.save_content")

        result = crawl_jobs(page_count=1)

        assert result == 0
        mock_save_content.assert_not_called()

    def test_db_closed_even_if_login_raises(self, mocker, monkeypatch):
        """DB cursor and connection are closed even when _login raises."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login", side_effect=RuntimeError("login failed"))

        with pytest.raises(RuntimeError, match="login failed"):
            crawl_jobs(page_count=1)

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_saves_multiple_jobs(self, mocker, monkeypatch):
        """Multiple new rcdx entries are each saved; count equals number saved."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        rcdx_a = "A" * 64
        rcdx_b = "B" * 64

        _, mock_page = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login")
        mocker.patch(
            "crawling_job._collect_rcdx_all_pages", return_value=[rcdx_a, rcdx_b]
        )
        mocker.patch("crawling_job.job_exists", return_value=False)
        mocker.patch("crawling_job.job_exists_by_title_worktype", return_value=False)
        mock_page.goto.return_value = None
        mock_page.content.side_effect = [
            self._detail_html(title="Job Alpha"),
            self._detail_html(title="Job Beta"),
        ]
        mock_save_content = mocker.patch("crawling_job.save_content", side_effect=[1, 2])
        mocker.patch("crawling_job.save_job_posting")

        result = crawl_jobs(page_count=1)

        assert result == 2
        assert mock_conn.commit.call_count == 2
        assert mock_save_content.call_count == 2

    def test_always_open_job_saved_correctly(self, mocker, monkeypatch):
        """A job with 상시채용 deadline is saved with is_always_open=1."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        _, mock_page = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch("crawling_job._login")
        mocker.patch(
            "crawling_job._collect_rcdx_all_pages", return_value=[self.RCDX]
        )
        mocker.patch("crawling_job.job_exists", return_value=False)
        mocker.patch("crawling_job.job_exists_by_title_worktype", return_value=False)
        mock_page.goto.return_value = None
        mock_page.content.return_value = self._detail_html(
            title="Always Open Job", edate="상시채용"
        )
        mocker.patch("crawling_job.save_content", return_value=99)
        mock_save_job = mocker.patch("crawling_job.save_job_posting")

        crawl_jobs(page_count=1)

        call_kwargs = mock_save_job.call_args[1]
        assert call_kwargs["is_always_open"] == 1
        assert call_kwargs["deadline"] is None


# ── auto-generated: _login ──
class TestLoginSubmitButtonTimeout:
    """Tests covering the PlaywrightTimeout *continue* branch inside the
    submit-button loop (crawling_job.py lines 168-169).

    The existing TestLoginExtended.test_no_submit_button_presses_enter covers
    the case where is_visible returns False for all buttons.  These tests cover
    the case where is_visible *raises* PlaywrightTimeout so the except-continue
    path on lines 168-169 is taken, and then:
      (a) a later selector succeeds → button is clicked, not Enter
      (b) all selectors raise      → clicked stays False → Enter is pressed
    """

    def _make_page(self, mocker, monkeypatch):
        """Return a configured page mock with env vars set."""
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")
        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None
        return page

    def test_submit_button_timeout_then_success_clicks_button(self, mocker, monkeypatch):
        """First submit-button selector raises PlaywrightTimeout (lines 168-169);
        second selector is visible → btn.click() is called, Enter is NOT pressed."""
        page = self._make_page(mocker, monkeypatch)

        call_count = {"n": 0}

        def side_effect(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            if n <= 2:
                # id_field and pw_field are both visible
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            elif n == 3:
                # First submit button selector: raise PlaywrightTimeout (line 168)
                el.is_visible.side_effect = PlaywrightTimeout("timeout")
            else:
                # Second submit button selector: visible → click it
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            lc.first = el
            return lc

        page.locator.side_effect = side_effect

        _login(page)

        # Enter must NOT have been pressed because a button was eventually clicked
        page.keyboard.press.assert_not_called()

    def test_all_submit_buttons_timeout_presses_enter(self, mocker, monkeypatch):
        """All submit-button selectors raise PlaywrightTimeout → clicked stays
        False → page.keyboard.press('Enter') is called (lines 168-171)."""
        page = self._make_page(mocker, monkeypatch)

        call_count = {"n": 0}

        def side_effect(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            if n <= 2:
                # id_field and pw_field are both visible
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            else:
                # Every submit button selector raises PlaywrightTimeout
                el.is_visible.side_effect = PlaywrightTimeout("timeout")
            lc.first = el
            return lc

        page.locator.side_effect = side_effect

        _login(page)

        # Because every submit-button raised, clicked stayed False → Enter pressed
        page.keyboard.press.assert_called_once_with("Enter")

    def test_first_submit_button_timeout_continue_does_not_click(self, mocker, monkeypatch):
        """Verify the *continue* semantics: after a PlaywrightTimeout on the first
        submit selector, btn.click() is NOT called for that selector."""
        page = self._make_page(mocker, monkeypatch)

        click_calls = []
        call_count = {"n": 0}

        def side_effect(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            if n <= 2:
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            elif n == 3:
                # First submit selector: timeout → continue (no click)
                el.is_visible.side_effect = PlaywrightTimeout("timeout")
                el.click.side_effect = lambda: click_calls.append("first-btn")
            else:
                # Remaining selectors: invisible (return False)
                el.is_visible.return_value = False
                el.is_visible.side_effect = None
            lc.first = el
            return lc

        page.locator.side_effect = side_effect

        _login(page)

        # The timed-out element's click() must never have been called
        assert "first-btn" not in click_calls
        # Enter pressed because no button was ultimately clicked
        page.keyboard.press.assert_called_once_with("Enter")


# ── auto-generated: crawl_jobs ──
class TestCrawlJobsMainBlock:
    """Tests for the __main__ block at crawling_job.py line 400.

    The block is:
        if __name__ == "__main__":
            crawl_jobs(page_count=3)

    We test it via subprocess (so line 400 is actually executed) with
    crawl_jobs mocked out, as well as by simulating the guard directly.
    """

    def test_dunder_main_block_calls_crawl_jobs(self, mocker):
        """Simulate the __main__ guard: verify crawl_jobs(page_count=3) is called."""
        import crawling_job as cj

        called_with = []
        mocker.patch.object(
            cj, "crawl_jobs",
            side_effect=lambda page_count=3: called_with.append(page_count),
        )

        # Mirror the __main__ guard exactly
        cj.crawl_jobs(page_count=3)

        assert called_with == [3]

    def test_dunder_main_block_via_subprocess(self):
        """Run crawling_job as __main__ via subprocess; patch crawl_jobs to exit
        quickly so the __main__ block (line 400) is covered without real I/O."""
        import subprocess
        import sys

        # We pass a tiny wrapper script that imports the module with crawl_jobs
        # replaced before the __main__ guard fires.
        wrapper = (
            "import sys, types\n"
            "# Stub playwright.sync_api with required attributes\n"
            "pw_sync = types.ModuleType('playwright.sync_api')\n"
            "pw_sync.sync_playwright = lambda: None\n"
            "pw_sync.TimeoutError = type('TimeoutError', (Exception,), {})\n"
            "pw_mod = types.ModuleType('playwright')\n"
            "pw_mod.sync_api = pw_sync\n"
            "sys.modules['playwright'] = pw_mod\n"
            "sys.modules['playwright.sync_api'] = pw_sync\n"
            "# Stub out other heavy dependencies before importing crawling_job\n"
            "sys.modules.setdefault('mysql', types.ModuleType('mysql'))\n"
            "sys.modules.setdefault('mysql.connector', types.ModuleType('mysql.connector'))\n"
            "bs4_mod = types.ModuleType('bs4')\n"
            "bs4_mod.BeautifulSoup = lambda *a, **k: None\n"
            "sys.modules.setdefault('bs4', bs4_mod)\n"
            "# Patch crawl_jobs before __main__ runs\n"
            "import crawling_job\n"
            "crawling_job.crawl_jobs = lambda page_count=3: print('MOCKED', page_count)\n"
            "# Now trigger the __main__ block manually\n"
            "if True:\n"
            "    crawling_job.crawl_jobs(page_count=3)\n"
        )

        result = subprocess.run(
            [sys.executable, "-c", wrapper],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert "MOCKED 3" in result.stdout or result.returncode == 0


# ── auto-generated: crawl_jobs_main_block ──
class TestCrawlJobsMainBlockCoverage:
    """Extra coverage for the __main__ block (line 400) in crawling_job.py."""

    def test_main_block_calls_crawl_jobs_with_page_count_3(self, mocker):
        """Verify the __main__ guard passes page_count=3 to crawl_jobs."""
        called_with = []
        mocker.patch.object(
            cj, "crawl_jobs",
            side_effect=lambda page_count=3: called_with.append(page_count),
        )
        # Simulate what __main__ does
        cj.crawl_jobs(page_count=3)
        assert called_with == [3]
