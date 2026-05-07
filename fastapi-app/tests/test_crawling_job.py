import sys
import pytest
from datetime import date
from bs4 import BeautifulSoup
import crawling_job as _crawling_job_module
from crawling_job import (
    _parse_deadline, _span_text, _parse_detail, _extract_rcdx_list,
    get_db_connection, DB_CONFIG, job_exists, job_exists_by_title_worktype,
    SOURCE_NAME, save_content, save_job_posting, _login, LOGIN_URL,
    _collect_rcdx_all_pages, LIST_URL,
)


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
        mock_connect = mocker.patch("mysql.connector.connect")
        mock_conn = mocker.MagicMock()
        mock_connect.return_value = mock_conn

        result = get_db_connection()

        mock_connect.assert_called_once_with(**DB_CONFIG)
        assert result is mock_conn

    def test_passes_db_config_values(self, mocker):
        mock_connect = mocker.patch("mysql.connector.connect")

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
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
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
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

        page = mocker.MagicMock()
        page.goto.return_value = None

        call_count = {"n": 0}
        id_selectors_count = 6
        pw_selectors_count = 6

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
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
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
        # Patch datetime on the real module object (bound at import time), not via
        # sys.modules string lookup, to avoid interference from test_scheduler.py
        # replacing sys.modules["crawling_job"] with a mock.
        mock_dt = mocker.patch.object(_crawling_job_module, "datetime")
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


# ── auto-generated: _login_exception_branches ──
class TestLoginExceptionBranches:
    """Tests for PlaywrightTimeout continue branches and Enter fallback in _login."""

    def _setup_env(self, monkeypatch):
        monkeypatch.setenv("SAINT_ID", "testuser")
        monkeypatch.setenv("SAINT_PW", "testpass")

    def test_timeout_on_id_selector_continues_to_next_selector(self, mocker, monkeypatch):
        """PlaywrightTimeout on first id selector is caught and loop continues to next selector."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        self._setup_env(monkeypatch)

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None

        call_count = {"n": 0}

        def make_locator(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First id selector raises PlaywrightTimeout on is_visible
                el.is_visible.side_effect = PlaywrightTimeout("timeout on id selector 1")
            elif call_count["n"] == 2:
                # Second id selector succeeds — becomes id_field
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            else:
                # All pw selectors: first one is visible — becomes pw_field
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            lc.first = el
            return lc

        page.locator.side_effect = make_locator

        # Should not raise; timeout on id selector 1 is caught and loop continues
        _login(page)

        # fill was called on both found fields
        assert page.locator.call_count >= 2

    def test_timeout_on_pw_selector_continues_to_next_selector(self, mocker, monkeypatch):
        """PlaywrightTimeout on first pw selector is caught; loop continues until a visible pw field is found."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        self._setup_env(monkeypatch)

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None

        id_selectors_count = 6
        call_count = {"n": 0}

        def make_locator(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            if n == 1:
                # First id selector is visible → id_field found immediately
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            elif n == id_selectors_count + 1:
                # First pw selector times out
                el.is_visible.side_effect = PlaywrightTimeout("timeout on pw selector 1")
            else:
                # All other pw selectors: second pw selector visible → pw_field
                el.is_visible.return_value = True
                el.is_visible.side_effect = None
            lc.first = el
            return lc

        page.locator.side_effect = make_locator

        _login(page)

        page.wait_for_url.assert_called_once()

    def test_all_submit_button_selectors_timeout_falls_back_to_enter(self, mocker, monkeypatch):
        """When every submit-button locator raises PlaywrightTimeout, page.keyboard.press('Enter') is called."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        self._setup_env(monkeypatch)

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None

        id_selectors_count = 6   # number of id selectors
        pw_selectors_count = 6   # number of pw selectors
        call_count = {"n": 0}

        def make_locator(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            if n <= id_selectors_count + pw_selectors_count:
                # id and pw selectors: first of each returns visible
                if n == 1 or n == id_selectors_count + 1:
                    el.is_visible.return_value = True
                    el.is_visible.side_effect = None
                else:
                    el.is_visible.return_value = False
                    el.is_visible.side_effect = None
            else:
                # All submit button selectors time out
                el.is_visible.side_effect = PlaywrightTimeout("submit btn timeout")
            lc.first = el
            return lc

        page.locator.side_effect = make_locator

        _login(page)

        # Because no submit button was clicked, Enter must be pressed as fallback
        page.keyboard.press.assert_called_once_with("Enter")

    def test_submit_button_timeout_does_not_prevent_successful_login(self, mocker, monkeypatch):
        """Enter fallback after all submit-button timeouts still reaches wait_for_url."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        self._setup_env(monkeypatch)

        page = mocker.MagicMock()
        page.goto.return_value = None
        page.url = "https://job.sogang.ac.kr/main/index.aspx"
        page.wait_for_url.return_value = None

        submit_selectors_count = 5
        id_pw_selectors_count = 12  # 6 id + 6 pw
        call_count = {"n": 0}

        def make_locator(sel):
            lc = mocker.MagicMock()
            el = mocker.MagicMock()
            call_count["n"] += 1
            n = call_count["n"]
            if n <= id_pw_selectors_count:
                if n == 1 or n == 7:
                    el.is_visible.return_value = True
                    el.is_visible.side_effect = None
                else:
                    el.is_visible.return_value = False
                    el.is_visible.side_effect = None
            else:
                el.is_visible.side_effect = PlaywrightTimeout("timeout")
            lc.first = el
            return lc

        page.locator.side_effect = make_locator

        _login(page)

        page.wait_for_url.assert_called_once()
        page.keyboard.press.assert_called_once_with("Enter")


# ── auto-generated: _parse_detail_error_handling ──
class TestParseDetailErrorHandling:
    """Tests for error/fallback branches in _parse_detail."""

    def test_script_and_style_tags_are_decomposed_from_alltext(self):
        """script and style tags inside ALLTEXT are removed from raw_content."""
        html = """
        <html><body>
          <span id="Title">Test Job</span>
          <span id="RUDate">2026-04-01</span>
          <span id="RecomEmp">정규직</span>
          <span id="WorkType">정규직</span>
          <span id="Duty">개발</span>
          <span id="Edate">2026-06-01 정시</span>
          <span id="ALLTEXT">
            본문 텍스트
            <script>alert('xss')</script>
            <style>.hidden { display: none; }</style>
            추가 내용
          </span>
        </body></html>
        """
        result = _parse_detail(html)
        assert "alert" not in result["raw_content"]
        assert ".hidden" not in result["raw_content"]
        assert "본문 텍스트" in result["raw_content"]
        assert "추가 내용" in result["raw_content"]

    def test_missing_alltext_element_returns_empty_raw_content(self):
        """When ALLTEXT span is absent, raw_content falls back to empty string."""
        html = """
        <html><body>
          <span id="Title">No Content Job</span>
          <span id="RUDate">2026-03-15</span>
          <span id="RecomEmp">계약직</span>
          <span id="WorkType">계약직</span>
          <span id="Duty">기타</span>
          <span id="Edate">상시채용</span>
        </body></html>
        """
        result = _parse_detail(html)
        assert result["raw_content"] == ""
        assert result["title"] == "No Content Job"
        assert result["is_always_open"] == 1

    def test_invalid_ru_date_format_results_in_none_posted_at(self):
        """When RUDate is an invalid date string, posted_at is None (ValueError caught)."""
        html = """
        <html><body>
          <span id="Title">Bad Date Job</span>
          <span id="RUDate">not-a-date</span>
          <span id="RecomEmp">인턴</span>
          <span id="WorkType">인턴직</span>
          <span id="Duty">기타</span>
          <span id="Edate">2026-07-01 정시</span>
          <span id="ALLTEXT">내용</span>
        </body></html>
        """
        result = _parse_detail(html)
        # "not-a-date" doesn't match "%Y-%m-%d" → ValueError → posted_at stays None
        assert result["posted_at"] is None
        assert result["title"] == "Bad Date Job"

    def test_empty_ru_date_results_in_none_posted_at(self):
        """When RUDate span is absent, posted_at is None without raising."""
        html = """
        <html><body>
          <span id="Title">No Date Job</span>
          <span id="RecomEmp">인턴</span>
          <span id="WorkType">인턴직</span>
          <span id="Duty">기타</span>
          <span id="Edate">2026-07-01 정시</span>
          <span id="ALLTEXT">내용</span>
        </body></html>
        """
        result = _parse_detail(html)
        assert result["posted_at"] is None


# ── auto-generated: crawl_jobs ──
class TestCrawlJobs:
    """Tests for the crawl_jobs() orchestration function."""

    RCDX_NEW = "A" * 64
    RCDX_EXISTING = "B" * 64
    RCDX_NO_TITLE = "C" * 64
    RCDX_DUP_TITLE = "D" * 64
    RCDX_TIMEOUT = "E" * 64

    def _detail_fields(self, title="Test Job"):
        return {
            "title": title,
            "employment": "인턴",
            "work_type": "인턴직",
            "duty": "기타",
            "deadline": None,
            "is_always_open": 1,
            "posted_at": None,
            "raw_content": "직무 내용",
        }

    def _setup_playwright_mocks(self, mocker):
        """Return a mock page and wire up sync_playwright context manager."""
        mock_page = mocker.MagicMock()
        mock_context = mocker.MagicMock()
        mock_browser = mocker.MagicMock()
        mock_pw = mocker.MagicMock()

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_pw.chromium.launch.return_value = mock_browser

        mock_sync_playwright = mocker.MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = mock_pw
        mock_sync_playwright.return_value.__exit__.return_value = False

        mocker.patch.object(_crawling_job_module, "sync_playwright", mock_sync_playwright)
        return mock_page, mock_browser

    def _setup_db_mocks(self, mocker):
        """Return mock conn and cursor."""
        mock_cursor = mocker.MagicMock()
        mock_conn = mocker.MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mocker.patch.object(_crawling_job_module, "get_db_connection", return_value=mock_conn)
        return mock_conn, mock_cursor

    def test_saves_new_job_and_returns_count(self, mocker):
        """A new rcdx that passes all checks is saved; saved_count is returned."""
        mock_page, mock_browser = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch.object(_crawling_job_module, "_login")
        mocker.patch.object(
            _crawling_job_module, "_collect_rcdx_all_pages",
            return_value=[self.RCDX_NEW],
        )
        mocker.patch.object(_crawling_job_module, "job_exists", return_value=False)
        mocker.patch.object(_crawling_job_module, "job_exists_by_title_worktype", return_value=False)
        mocker.patch.object(
            _crawling_job_module, "_parse_detail",
            return_value=self._detail_fields("Test Job"),
        )
        mock_save_content = mocker.patch.object(
            _crawling_job_module, "save_content", return_value=42
        )
        mock_save_posting = mocker.patch.object(_crawling_job_module, "save_job_posting")

        result = _crawling_job_module.crawl_jobs(page_count=1)

        assert result == 1
        mock_save_content.assert_called_once()
        mock_save_posting.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_skips_already_existing_rcdx(self, mocker):
        """rcdx whose URL already exists in the DB is skipped without calling parse/save."""
        mock_page, _ = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch.object(_crawling_job_module, "_login")
        mocker.patch.object(
            _crawling_job_module, "_collect_rcdx_all_pages",
            return_value=[self.RCDX_EXISTING],
        )
        # job_exists returns True → should skip
        mocker.patch.object(_crawling_job_module, "job_exists", return_value=True)
        mock_parse = mocker.patch.object(_crawling_job_module, "_parse_detail")
        mock_save = mocker.patch.object(_crawling_job_module, "save_content")

        result = _crawling_job_module.crawl_jobs(page_count=1)

        assert result == 0
        mock_parse.assert_not_called()
        mock_save.assert_not_called()

    def test_skips_job_with_empty_title(self, mocker):
        """A detail page with no title is skipped; save functions are not called."""
        mock_page, _ = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch.object(_crawling_job_module, "_login")
        mocker.patch.object(
            _crawling_job_module, "_collect_rcdx_all_pages",
            return_value=[self.RCDX_NO_TITLE],
        )
        mocker.patch.object(_crawling_job_module, "job_exists", return_value=False)
        mocker.patch.object(
            _crawling_job_module, "_parse_detail",
            return_value=self._detail_fields(""),  # empty title
        )
        mock_save = mocker.patch.object(_crawling_job_module, "save_content")

        result = _crawling_job_module.crawl_jobs(page_count=1)

        assert result == 0
        mock_save.assert_not_called()

    def test_skips_duplicate_title_worktype(self, mocker):
        """rcdx whose title+work_type combo already exists is skipped."""
        mock_page, _ = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch.object(_crawling_job_module, "_login")
        mocker.patch.object(
            _crawling_job_module, "_collect_rcdx_all_pages",
            return_value=[self.RCDX_DUP_TITLE],
        )
        mocker.patch.object(_crawling_job_module, "job_exists", return_value=False)
        mocker.patch.object(
            _crawling_job_module, "_parse_detail",
            return_value=self._detail_fields("Duplicate Job"),
        )
        # job_exists_by_title_worktype returns True → duplicate
        mocker.patch.object(
            _crawling_job_module, "job_exists_by_title_worktype", return_value=True
        )
        mock_save = mocker.patch.object(_crawling_job_module, "save_content")

        result = _crawling_job_module.crawl_jobs(page_count=1)

        assert result == 0
        mock_save.assert_not_called()

    def test_page_goto_timeout_continues_to_next_rcdx(self, mocker):
        """PlaywrightTimeout on page.goto for a detail URL is caught; processing continues."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        mock_page, _ = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch.object(_crawling_job_module, "_login")
        mocker.patch.object(
            _crawling_job_module, "_collect_rcdx_all_pages",
            return_value=[self.RCDX_TIMEOUT, self.RCDX_NEW],
        )

        def job_exists_side_effect(cursor, url):
            return False  # both rcdx are new

        mocker.patch.object(_crawling_job_module, "job_exists", side_effect=job_exists_side_effect)
        mocker.patch.object(_crawling_job_module, "job_exists_by_title_worktype", return_value=False)

        # First goto (RCDX_TIMEOUT) raises; second (RCDX_NEW) succeeds
        mock_page.goto.side_effect = [
            PlaywrightTimeout("detail page timeout"),
            None,
        ]
        mocker.patch.object(
            _crawling_job_module, "_parse_detail",
            return_value=self._detail_fields("Surviving Job"),
        )
        mock_save_content = mocker.patch.object(
            _crawling_job_module, "save_content", return_value=7
        )
        mocker.patch.object(_crawling_job_module, "save_job_posting")

        result = _crawling_job_module.crawl_jobs(page_count=1)

        # Only the non-timeout rcdx is saved
        assert result == 1
        mock_save_content.assert_called_once()

    def test_db_connection_closed_on_exception(self, mocker):
        """conn.close() and cursor.close() are called even when an exception occurs."""
        mock_page, _ = self._setup_playwright_mocks(mocker)
        mock_conn, mock_cursor = self._setup_db_mocks(mocker)

        mocker.patch.object(_crawling_job_module, "_login")
        mocker.patch.object(
            _crawling_job_module, "_collect_rcdx_all_pages",
            side_effect=RuntimeError("unexpected error"),
        )

        with pytest.raises(RuntimeError, match="unexpected error"):
            _crawling_job_module.crawl_jobs(page_count=1)

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
