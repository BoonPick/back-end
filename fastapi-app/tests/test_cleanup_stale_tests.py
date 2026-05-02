"""Tests for scripts/cleanup_stale_tests.py."""
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from cleanup_stale_tests import cleanup_stale_tests, get_main_functions


# ---------------------------------------------------------------------------
# get_main_functions
# ---------------------------------------------------------------------------

def test_get_main_functions_returns_function_names(tmp_path):
    src = tmp_path / "main.py"
    src.write_text(textwrap.dedent("""\
        def foo():
            pass

        def bar(x):
            return x
    """))
    result = get_main_functions(src)
    assert "foo" in result
    assert "bar" in result


def test_get_main_functions_includes_async(tmp_path):
    src = tmp_path / "main.py"
    src.write_text("async def async_fn(): pass\n")
    result = get_main_functions(src)
    assert "async_fn" in result


def test_get_main_functions_empty_file(tmp_path):
    src = tmp_path / "main.py"
    src.write_text("")
    result = get_main_functions(src)
    assert result == set()


def test_get_main_functions_nested_not_excluded(tmp_path):
    src = tmp_path / "main.py"
    src.write_text(textwrap.dedent("""\
        def outer():
            def inner():
                pass
    """))
    result = get_main_functions(src)
    assert "outer" in result
    assert "inner" in result


# ---------------------------------------------------------------------------
# cleanup_stale_tests
# ---------------------------------------------------------------------------

MARKER_BLOCK = textwrap.dedent("""\
    # ── auto-generated: stale_func ──
    class TestStaleFunc:
        def test_something(self):
            pass
""")

LIVE_BLOCK = textwrap.dedent("""\
    # ── auto-generated: live_func ──
    class TestLiveFunc:
        def test_live(self):
            assert True
""")


def test_removes_block_for_missing_function(tmp_path):
    test_file = tmp_path / "test_main.py"
    test_file.write_text(MARKER_BLOCK)
    removed = cleanup_stale_tests(test_file, {"other_func"})
    assert "stale_func" in removed
    assert "TestStaleFunc" not in test_file.read_text()


def test_keeps_block_for_existing_function(tmp_path):
    test_file = tmp_path / "test_main.py"
    test_file.write_text(LIVE_BLOCK)
    removed = cleanup_stale_tests(test_file, {"live_func"})
    assert removed == []
    assert "TestLiveFunc" in test_file.read_text()


def test_removes_only_stale_keeps_live(tmp_path):
    test_file = tmp_path / "test_main.py"
    test_file.write_text(MARKER_BLOCK + "\n" + LIVE_BLOCK)
    removed = cleanup_stale_tests(test_file, {"live_func"})
    assert "stale_func" in removed
    content = test_file.read_text()
    assert "TestStaleFunc" not in content
    assert "TestLiveFunc" in content


def test_no_markers_returns_empty(tmp_path):
    test_file = tmp_path / "test_main.py"
    test_file.write_text("def test_plain(): pass\n")
    removed = cleanup_stale_tests(test_file, set())
    assert removed == []


def test_file_unchanged_when_nothing_removed(tmp_path):
    original = "def test_plain(): pass\n"
    test_file = tmp_path / "test_main.py"
    test_file.write_text(original)
    cleanup_stale_tests(test_file, set())
    assert test_file.read_text() == original


def test_removes_multiple_stale_blocks(tmp_path):
    block_a = "# ── auto-generated: alpha ──\nclass TestAlpha:\n    def test_a(self): pass\n"
    block_b = "# ── auto-generated: beta ──\nclass TestBeta:\n    def test_b(self): pass\n"
    test_file = tmp_path / "test_main.py"
    test_file.write_text(block_a + "\n" + block_b)
    removed = cleanup_stale_tests(test_file, set())
    assert "alpha" in removed
    assert "beta" in removed
    content = test_file.read_text()
    assert "TestAlpha" not in content
    assert "TestBeta" not in content
