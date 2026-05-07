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


# ── auto-generated: _call_anthropic ──
import os
from unittest.mock import MagicMock, patch
from llm import _call_anthropic


class TestCallAnthropic:
    def test_returns_text_from_message_content(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="anthropic response")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("anthropic.Anthropic", return_value=mock_client) as mock_cls:
            result = _call_anthropic("test prompt")

        mock_cls.assert_called_once_with(api_key="test-key")
        assert result == "anthropic response"

    def test_calls_correct_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="ok")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("anthropic.Anthropic", return_value=mock_client):
            _call_anthropic("prompt")

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-20250514" or \
               call_kwargs[1].get("model") == "claude-sonnet-4-20250514" or \
               "claude-sonnet-4-20250514" in str(call_kwargs)

    def test_passes_prompt_as_user_message(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="ok")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("anthropic.Anthropic", return_value=mock_client):
            _call_anthropic("my test prompt")

        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages") or call_kwargs[0][0]
        assert any(m.get("content") == "my test prompt" for m in messages if isinstance(m, dict))

    def test_uses_env_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-secret-key")
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="ok")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("anthropic.Anthropic", return_value=mock_client) as mock_cls:
            _call_anthropic("p")

        mock_cls.assert_called_once_with(api_key="env-secret-key")


# ── auto-generated: _call_openai ──
from llm import _call_openai


class TestCallOpenai:
    def test_returns_content_from_choices(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="openai response"))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client) as mock_cls:
            result = _call_openai("test prompt")

        mock_cls.assert_called_once_with(api_key="test-openai-key")
        assert result == "openai response"

    def test_uses_default_model_when_env_not_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            _call_openai("prompt")

        call_kwargs = mock_client.chat.completions.create.call_args
        model = call_kwargs.kwargs.get("model") or call_kwargs[1].get("model")
        assert model == "gpt-4o-mini"

    def test_uses_custom_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            _call_openai("prompt")

        call_kwargs = mock_client.chat.completions.create.call_args
        model = call_kwargs.kwargs.get("model") or call_kwargs[1].get("model")
        assert model == "gpt-4o"

    def test_passes_system_and_user_messages(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_client):
            _call_openai("hello user")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        roles = [m["role"] for m in messages]
        assert "system" in roles
        assert "user" in roles
        user_msg = next(m for m in messages if m["role"] == "user")
        assert user_msg["content"] == "hello user"


# ── auto-generated: get_llm_recommendation ──
from llm import get_llm_recommendation


class TestGetLlmRecommendation:
    def test_uses_anthropic_when_anthropic_key_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        response_json = '{"matchScore": 70, "matchReason": "reason", "preparationTips": ["tip"]}'

        with patch("llm._call_anthropic", return_value=response_json) as mock_ant:
            with patch("llm._call_openai") as mock_oai:
                result = get_llm_recommendation(["AI"], "AI 특강", "announcement", "내용")

        mock_ant.assert_called_once()
        mock_oai.assert_not_called()
        assert result["matchScore"] == 70

    def test_uses_openai_when_only_openai_key_set(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        response_json = '{"matchScore": 55, "matchReason": "r", "preparationTips": []}'

        with patch("llm._call_openai", return_value=response_json) as mock_oai:
            with patch("llm._call_anthropic") as mock_ant:
                result = get_llm_recommendation(["장학금"], "장학금 안내", "scholarship", "내용")

        mock_oai.assert_called_once()
        mock_ant.assert_not_called()
        assert result["matchScore"] == 55

    def test_returns_fallback_when_no_keys_set(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        result = get_llm_recommendation(["AI"], "AI 특강 안내", "announcement", "")

        assert "matchScore" in result
        assert "matchReason" in result
        assert "preparationTips" in result

    def test_returns_fallback_on_llm_exception(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with patch("llm._call_anthropic", side_effect=RuntimeError("API failure")):
            result = get_llm_recommendation(["장학금"], "장학금 안내", "scholarship", "내용")

        assert "matchScore" in result
        assert "preparationTips" in result

    def test_anthropic_key_takes_priority_over_openai(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        response_json = '{"matchScore": 90, "matchReason": "r", "preparationTips": ["t"]}'

        with patch("llm._call_anthropic", return_value=response_json) as mock_ant:
            with patch("llm._call_openai") as mock_oai:
                get_llm_recommendation(["취업"], "취업 박람회", "job", "내용")

        mock_ant.assert_called_once()
        mock_oai.assert_not_called()

    def test_returns_dict_with_required_keys(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        response_json = '{"matchScore": 42, "matchReason": "이유", "preparationTips": ["a", "b"]}'

        with patch("llm._call_anthropic", return_value=response_json):
            result = get_llm_recommendation(["kw"], "title", "cat", "content")

        assert isinstance(result, dict)
        assert "matchScore" in result
        assert "matchReason" in result
        assert "preparationTips" in result
