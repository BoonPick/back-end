"""
llm.py 자동 생성 테스트
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from llm import get_llm_recommendation


# ── auto-generated: get_llm_recommendation ──────────────────────────────────
class TestGetLlmRecommendation:
    """Tests for get_llm_recommendation function."""

    def test_uses_anthropic_when_anthropic_key_set(self, monkeypatch):
        """ANTHROPIC_API_KEY가 설정되면 _call_anthropic을 사용한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        expected_result = {"matchScore": 80, "matchReason": "test", "preparationTips": ["a"]}
        mock_call_anthropic = MagicMock(return_value='{"matchScore": 80, "matchReason": "test", "preparationTips": ["a"]}')
        mock_parse_json = MagicMock(return_value=expected_result)
        mock_build_prompt = MagicMock(return_value="built prompt")

        with patch("llm._call_anthropic", mock_call_anthropic), \
             patch("llm._parse_json", mock_parse_json), \
             patch("llm._build_user_prompt", mock_build_prompt):
            result = get_llm_recommendation(["kw1"], "title", "cat", "content")

        mock_build_prompt.assert_called_once_with(["kw1"], "title", "cat", "content")
        mock_call_anthropic.assert_called_once_with("built prompt")
        assert result == expected_result

    def test_uses_openai_when_only_openai_key_set(self, monkeypatch):
        """ANTHROPIC_API_KEY가 없고 OPENAI_API_KEY만 있으면 _call_openai를 사용한다."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

        expected_result = {"recommendation": "openai result"}
        mock_call_openai = MagicMock(return_value='{"recommendation": "openai result"}')
        mock_parse_json = MagicMock(return_value=expected_result)
        mock_build_prompt = MagicMock(return_value="openai prompt")

        with patch("llm._call_openai", mock_call_openai), \
             patch("llm._parse_json", mock_parse_json), \
             patch("llm._build_user_prompt", mock_build_prompt):
            result = get_llm_recommendation(["kw"], "t", "c", "raw")

        mock_call_openai.assert_called_once_with("openai prompt")
        assert result == expected_result

    def test_anthropic_takes_priority_over_openai(self, monkeypatch):
        """두 키가 모두 있으면 ANTHROPIC_API_KEY가 우선한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

        mock_call_anthropic = MagicMock(return_value='{}')
        mock_call_openai = MagicMock(return_value='{}')
        mock_parse_json = MagicMock(return_value={})
        mock_build_prompt = MagicMock(return_value="prompt")

        with patch("llm._call_anthropic", mock_call_anthropic), \
             patch("llm._call_openai", mock_call_openai), \
             patch("llm._parse_json", mock_parse_json), \
             patch("llm._build_user_prompt", mock_build_prompt):
            get_llm_recommendation(["k"], "t", "c", "r")

        mock_call_anthropic.assert_called_once()
        mock_call_openai.assert_not_called()

    def test_fallback_when_no_api_keys(self, monkeypatch):
        """API 키가 모두 없으면 _fallback을 반환한다."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        fallback_result = {"fallback": True, "keywords": ["k1"]}
        mock_fallback = MagicMock(return_value=fallback_result)

        with patch("llm._fallback", mock_fallback):
            result = get_llm_recommendation(["k1"], "my title", "cat", "content")

        mock_fallback.assert_called_once_with(["k1"], "my title")
        assert result == fallback_result

    def test_fallback_on_llm_call_exception(self, monkeypatch):
        """LLM 호출 중 예외 발생 시 _fallback을 반환한다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        fallback_result = {"fallback": True}
        mock_call_anthropic = MagicMock(side_effect=RuntimeError("API timeout"))
        mock_fallback = MagicMock(return_value=fallback_result)
        mock_build_prompt = MagicMock(return_value="prompt")

        with patch("llm._call_anthropic", mock_call_anthropic), \
             patch("llm._fallback", mock_fallback), \
             patch("llm._build_user_prompt", mock_build_prompt):
            result = get_llm_recommendation(["k"], "t", "c", "r")

        mock_fallback.assert_called_once_with(["k"], "t")
        assert result == fallback_result

    def test_fallback_on_parse_json_exception(self, monkeypatch):
        """_parse_json에서 예외 발생 시 _fallback을 반환한다."""
        monkeypatch.setenv("OPENAI_API_KEY", "key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        fallback_result = {"fallback": True}
        mock_call_openai = MagicMock(return_value="not valid json")
        mock_parse_json = MagicMock(side_effect=json.JSONDecodeError("err", "doc", 0))
        mock_fallback = MagicMock(return_value=fallback_result)
        mock_build_prompt = MagicMock(return_value="prompt")

        with patch("llm._call_openai", mock_call_openai), \
             patch("llm._parse_json", mock_parse_json), \
             patch("llm._fallback", mock_fallback), \
             patch("llm._build_user_prompt", mock_build_prompt):
            result = get_llm_recommendation(["k"], "t", "c", "r")

        assert result == fallback_result
        mock_fallback.assert_called_once_with(["k"], "t")

    def test_exception_prints_error_message(self, monkeypatch, capsys):
        """예외 발생 시 에러 메시지가 출력된다."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        mock_call_anthropic = MagicMock(side_effect=ValueError("custom error msg"))
        mock_fallback = MagicMock(return_value={})
        mock_build_prompt = MagicMock(return_value="prompt")

        with patch("llm._call_anthropic", mock_call_anthropic), \
             patch("llm._fallback", mock_fallback), \
             patch("llm._build_user_prompt", mock_build_prompt):
            get_llm_recommendation(["k"], "t", "cat", "content")

        captured = capsys.readouterr()
        assert "LLM error: custom error msg" in captured.out
