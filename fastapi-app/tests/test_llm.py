import pytest
from llm import _build_user_prompt, _parse_json, _fallback


class TestBuildUserPrompt:
    def test_contains_keywords(self):
        prompt = _build_user_prompt(["AI", "머신러닝"], "AI 특강", "announcement", "내용")
        assert "AI" in prompt
        assert "머신러닝" in prompt

    def test_contains_title_and_category(self):
        prompt = _build_user_prompt(["키워드"], "제목입니다", "scholarship", "내용")
        assert "제목입니다" in prompt
        assert "scholarship" in prompt

    def test_truncates_long_content(self):
        long_content = "a" * 5000
        prompt = _build_user_prompt(["kw"], "title", "cat", long_content)
        assert "a" * 3001 not in prompt

    def test_empty_keywords(self):
        prompt = _build_user_prompt([], "제목", "cat", "내용")
        assert "matchScore" in prompt


class TestParseJson:
    def test_parses_plain_json(self):
        text = '{"matchScore": 80, "matchReason": "이유", "preparationTips": ["팁1"]}'
        result = _parse_json(text)
        assert result["matchScore"] == 80

    def test_parses_markdown_fenced_json(self):
        text = '```json\n{"matchScore": 50, "matchReason": "r", "preparationTips": []}\n```'
        result = _parse_json(text)
        assert result["matchScore"] == 50

    def test_parses_fenced_without_language(self):
        text = '```\n{"matchScore": 30, "matchReason": "r", "preparationTips": []}\n```'
        result = _parse_json(text)
        assert result["matchScore"] == 30

    def test_raises_on_invalid_json(self):
        with pytest.raises(Exception):
            _parse_json("not json")


class TestFallback:
    def test_high_score_when_keyword_in_title(self):
        result = _fallback(["장학금"], "2025 장학금 모집")
        assert result["matchScore"] >= 30

    def test_low_score_when_no_match(self):
        result = _fallback(["AI"], "체육관 이용 안내")
        assert result["matchScore"] <= 20

    def test_returns_required_keys(self):
        result = _fallback(["키워드"], "제목")
        assert "matchScore" in result
        assert "matchReason" in result
        assert "preparationTips" in result
        assert isinstance(result["preparationTips"], list)

    def test_score_capped_at_100(self):
        keywords = ["a", "b", "c", "d", "e"]
        result = _fallback(keywords, "a b c d e")
        assert result["matchScore"] <= 100

    def test_case_insensitive_match(self):
        result_lower = _fallback(["ai"], "AI 특강 안내")
        result_upper = _fallback(["AI"], "ai 특강 안내")
        assert result_lower["matchScore"] > 10
        assert result_upper["matchScore"] > 10
