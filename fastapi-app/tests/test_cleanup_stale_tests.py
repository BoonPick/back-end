"""Tests for scripts/cleanup_stale_tests.py"""
import ast
import textwrap
from pathlib import Path

import pytest

from scripts.cleanup_stale_tests import cleanup_stale_tests, get_main_functions


# ---------------------------------------------------------------------------
# get_main_functions
# ---------------------------------------------------------------------------

def write_tmp(tmp_path: Path, filename: str, source: str) -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(source), encoding="utf-8")
    return p


class TestGetMainFunctions:
    def test_returns_top_level_function_names(self, tmp_path):
        p = write_tmp(tmp_path, "main.py", """
            def foo():
                pass

            def bar():
                pass
        """)
        result = get_main_functions(p)
        assert "foo" in result
        assert "bar" in result

    def test_returns_async_function_names(self, tmp_path):
        p = write_tmp(tmp_path, "main.py", """
            async def async_handler():
                pass
        """)
        result = get_main_functions(p)
        assert "async_handler" in result

    def test_returns_empty_set_for_no_functions(self, tmp_path):
        p = write_tmp(tmp_path, "main.py", "x = 1\n")
        assert get_main_functions(p) == set()

    def test_includes_nested_functions(self, tmp_path):
        p = write_tmp(tmp_path, "main.py", """
            def outer():
                def inner():
                    pass
        """)
        result = get_main_functions(p)
        assert "outer" in result
        assert "inner" in result

    def test_returns_set_type(self, tmp_path):
        p = write_tmp(tmp_path, "main.py", "def only_one(): pass\n")
        assert isinstance(get_main_functions(p), set)


# ---------------------------------------------------------------------------
# cleanup_stale_tests
# ---------------------------------------------------------------------------

MARKER_TEMPLATE = "# ── auto-generated: {name} ──\n"

STALE_BLOCK = """\
# ── auto-generated: old_func ──

class TestOldFunc:
    def test_something(self):
        pass
"""

LIVE_BLOCK = """\
# ── auto-generated: live_func ──

class TestLiveFunc:
    def test_something(self):
        pass
"""


class TestCleanupStaleTests:
    def test_removes_block_for_missing_function(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text(STALE_BLOCK, encoding="utf-8")

        removed = cleanup_stale_tests(test_py, main_functions=set())

        assert "old_func" in removed
        assert "TestOldFunc" not in test_py.read_text(encoding="utf-8")

    def test_keeps_block_for_existing_function(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text(LIVE_BLOCK, encoding="utf-8")

        removed = cleanup_stale_tests(test_py, main_functions={"live_func"})

        assert removed == []
        assert "TestLiveFunc" in test_py.read_text(encoding="utf-8")

    def test_removes_only_stale_blocks_mixed(self, tmp_path):
        content = LIVE_BLOCK + "\n" + STALE_BLOCK
        test_py = tmp_path / "test_main.py"
        test_py.write_text(content, encoding="utf-8")

        removed = cleanup_stale_tests(test_py, main_functions={"live_func"})

        text = test_py.read_text(encoding="utf-8")
        assert "old_func" in removed
        assert "TestOldFunc" not in text
        assert "TestLiveFunc" in text

    def test_returns_empty_list_when_nothing_removed(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text("def test_plain(): pass\n", encoding="utf-8")

        removed = cleanup_stale_tests(test_py, main_functions=set())

        assert removed == []

    def test_file_not_modified_when_nothing_removed(self, tmp_path):
        original = "def test_plain(): pass\n"
        test_py = tmp_path / "test_main.py"
        test_py.write_text(original, encoding="utf-8")
        mtime_before = test_py.stat().st_mtime

        cleanup_stale_tests(test_py, main_functions=set())

        assert test_py.read_text(encoding="utf-8") == original

    def test_multiple_stale_blocks_all_removed(self, tmp_path):
        block_a = "# ── auto-generated: gone_a ──\n\nclass TestGoneA:\n    pass\n\n"
        block_b = "# ── auto-generated: gone_b ──\n\nclass TestGoneB:\n    pass\n"
        test_py = tmp_path / "test_main.py"
        test_py.write_text(block_a + block_b, encoding="utf-8")

        removed = cleanup_stale_tests(test_py, main_functions=set())

        assert set(removed) == {"gone_a", "gone_b"}
        text = test_py.read_text(encoding="utf-8")
        assert "TestGoneA" not in text
        assert "TestGoneB" not in text
