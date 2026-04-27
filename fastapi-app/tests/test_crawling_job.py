import pytest
from datetime import date
from bs4 import BeautifulSoup
from crawling_job import _parse_deadline, _span_text, _parse_detail, _extract_rcdx_list


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
        html = f'<a href="/Recruit/RecruitView.aspx?rcdx={rcdx}&modalChk=Y">공고</a>'
        result = _extract_rcdx_list(html)
        assert rcdx in result

    def test_extracts_from_onclick(self):
        rcdx = "B" * 64
        html = f'<a onclick="openw(\'/Recruit/RecruitView.aspx?rcdx={rcdx}&m=Y\')">공고</a>'
        result = _extract_rcdx_list(html)
        assert rcdx in result

    def test_deduplicates(self):
        rcdx = "C" * 64
        html = (
            f'<a href="?rcdx={rcdx}">1</a>'
            f'<a href="?rcdx={rcdx}">2</a>'
        )
        result = _extract_rcdx_list(html)
        assert result.count(rcdx) == 1

    def test_empty_html(self):
        assert _extract_rcdx_list("") == []

    def test_ignores_short_rcdx(self):
        html = '<a href="?rcdx=SHORT">공고</a>'
        assert _extract_rcdx_list(html) == []
