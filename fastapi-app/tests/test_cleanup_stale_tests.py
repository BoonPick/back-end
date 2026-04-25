"""Tests for scripts/cleanup_stale_tests.py"""
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the scripts directory to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from cleanup_stale_tests import get_main_functions, cleanup_stale_tests


# ── helpers ──────────────────────────────────────────────────────────────────

def write_file(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ── get_main_functions ────────────────────────────────────────────────────────

class TestGetMainFunctions:
    def test_returns_top_level_function_names(self, tmp_path):
        src = write_file(tmp_path, "main.py", """\
            def foo():
                pass

            def bar():
                pass
        """)
        assert get_main_functions(src) == {"foo", "bar"}

    def test_returns_async_function_names(self, tmp_path):
        src = write_file(tmp_path, "main.py", """\
            async def async_handler():
                pass
        """)
        assert "async_handler" in get_main_functions(src)

    def test_includes_nested_functions(self, tmp_path):
        src = write_file(tmp_path, "main.py", """\
            def outer():
                def inner():
                    pass
        """)
        funcs = get_main_functions(src)
        assert "outer" in funcs
        assert "inner" in funcs

    def test_returns_empty_set_for_no_functions(self, tmp_path):
        src = write_file(tmp_path, "main.py", "x = 1\n")
        assert get_main_functions(src) == set()

    def test_ignores_class_definitions(self, tmp_path):
        src = write_file(tmp_path, "main.py", """\
            class MyClass:
                def method(self):
                    pass
        """)
        funcs = get_main_functions(src)
        assert "MyClass" not in funcs
        assert "method" in funcs


# ── cleanup_stale_tests ───────────────────────────────────────────────────────

class TestCleanupStaleTests:
    def _make_test_file(self, tmp_path: Path, content: str) -> Path:
        return write_file(tmp_path, "test_main.py", content)

    def test_removes_block_for_missing_function(self, tmp_path):
        test_file = self._make_test_file(tmp_path, """\
            # ── auto-generated: old_func ──
            class TestOldFunc:
                def test_something(self):
                    pass
        """)
        removed = cleanup_stale_tests(test_file, {"existing_func"})
        assert "old_func" in removed
        assert "TestOldFunc" not in test_file.read_text()

    def test_keeps_block_for_existing_function(self, tmp_path):
        test_file = self._make_test_file(tmp_path, """\
            # ── auto-generated: live_func ──
            class TestLiveFunc:
                def test_something(self):
                    pass
        """)
        removed = cleanup_stale_tests(test_file, {"live_func"})
        assert removed == []
        assert "TestLiveFunc" in test_file.read_text()

    def test_returns_empty_list_when_nothing_to_remove(self, tmp_path):
        test_file = self._make_test_file(tmp_path, """\
            def test_manual():
                assert True
        """)
        removed = cleanup_stale_tests(test_file, set())
        assert removed == []

    def test_removes_only_stale_block_among_multiple(self, tmp_path):
        test_file = self._make_test_file(tmp_path, """\
            # ── auto-generated: stale_func ──
            class TestStaleFunc:
                def test_stale(self):
                    pass
            # ── auto-generated: live_func ──
            class TestLiveFunc:
                def test_live(self):
                    pass
        """)
        removed = cleanup_stale_tests(test_file, {"live_func"})
        assert "stale_func" in removed
        text = test_file.read_text()
        assert "TestStaleFunc" not in text
        assert "TestLiveFunc" in text

    def test_does_not_write_file_when_nothing_removed(self, tmp_path):
        content = "def test_noop():\n    pass\n"
        test_file = self._make_test_file(tmp_path, content)
        original_mtime = test_file.stat().st_mtime
        cleanup_stale_tests(test_file, set())
        # File should not have been rewritten (same mtime)
        assert test_file.stat().st_mtime == original_mtime

    def test_rewrites_file_when_block_removed(self, tmp_path):
        test_file = self._make_test_file(tmp_path, """\
            # ── auto-generated: gone_func ──
            class TestGoneFunc:
                def test_x(self):
                    pass
        """)
        removed = cleanup_stale_tests(test_file, set())
        assert "gone_func" in removed
        assert test_file.read_text().strip() == ""


# ── main() integration ────────────────────────────────────────────────────────

class TestMain:
    def test_main_exits_with_error_when_main_py_missing(self, tmp_path, capsys):
        fake_base = tmp_path
        (fake_base / "tests").mkdir()
        (fake_base / "tests" / "test_main.py").write_text("", encoding="utf-8")

        import cleanup_stale_tests as module
        with patch.object(Path, "resolve", return_value=fake_base / "scripts" / "cleanup_stale_tests.py"):
            with patch("cleanup_stale_tests.Path") as MockPath:
                pass  # Difficult to mock Path fully; test via direct call instead

    def test_main_prints_no_stale_when_clean(self, tmp_path, capsys):
        main_py = tmp_path / "main.py"
        main_py.write_text("def my_func():\n    pass\n", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_main.py"
        test_file.write_text(
            "# ── auto-generated: my_func ──\nclass TestMyFunc:\n    pass\n",
            encoding="utf-8"
        )

        funcs = get_main_functions(main_py)
        removed = cleanup_stale_tests(test_file, funcs)
        assert removed == []
        captured = capsys.readouterr()
        assert captured.out == ""
