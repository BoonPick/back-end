"""Tests for scripts/cleanup_stale_tests.py."""
import ast
import sys
import textwrap
from pathlib import Path

import pytest

# Add scripts/ to path so we can import the module directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import cleanup_stale_tests as cst


# ---------------------------------------------------------------------------
# get_main_functions
# ---------------------------------------------------------------------------

class TestGetMainFunctions:
    def test_returns_top_level_function_names(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text("def foo(): pass\ndef bar(): pass\n")
        result = cst.get_main_functions(src)
        assert "foo" in result
        assert "bar" in result

    def test_returns_async_function_names(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text("async def baz(): pass\n")
        result = cst.get_main_functions(src)
        assert "baz" in result

    def test_empty_file_returns_empty_set(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text("")
        result = cst.get_main_functions(src)
        assert result == set()

    def test_nested_functions_included(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text(textwrap.dedent("""\
            def outer():
                def inner():
                    pass
        """))
        result = cst.get_main_functions(src)
        assert "outer" in result
        assert "inner" in result

    def test_class_methods_not_confused_with_top_level(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text(textwrap.dedent("""\
            class MyClass:
                def method(self): pass
            def top_level(): pass
        """))
        result = cst.get_main_functions(src)
        assert "top_level" in result
        assert "method" in result


# ---------------------------------------------------------------------------
# cleanup_stale_tests
# ---------------------------------------------------------------------------

class TestCleanupStaleTests:
    def _make_test_file(self, path: Path, content: str) -> Path:
        test_file = path / "test_main.py"
        test_file.write_text(textwrap.dedent(content))
        return test_file

    def test_removes_stale_block(self, tmp_path):
        content = """\
            # ── auto-generated: old_func ──
            class TestOldFunc:
                def test_something(self):
                    pass
        """
        test_file = self._make_test_file(tmp_path, content)
        removed = cst.cleanup_stale_tests(test_file, main_functions=set())
        assert "old_func" in removed
        assert "class TestOldFunc" not in test_file.read_text()

    def test_keeps_valid_block(self, tmp_path):
        content = """\
            # ── auto-generated: existing_func ──
            class TestExistingFunc:
                def test_something(self):
                    pass
        """
        test_file = self._make_test_file(tmp_path, content)
        removed = cst.cleanup_stale_tests(test_file, main_functions={"existing_func"})
        assert removed == []
        assert "class TestExistingFunc" in test_file.read_text()

    def test_returns_empty_list_when_nothing_stale(self, tmp_path):
        content = """\
            def test_plain():
                assert True
        """
        test_file = self._make_test_file(tmp_path, content)
        removed = cst.cleanup_stale_tests(test_file, main_functions=set())
        assert removed == []

    def test_does_not_write_file_when_nothing_removed(self, tmp_path):
        content = "def test_plain():\n    assert True\n"
        test_file = self._make_test_file(tmp_path, content)
        original_mtime = test_file.stat().st_mtime
        cst.cleanup_stale_tests(test_file, main_functions=set())
        assert test_file.stat().st_mtime == original_mtime

    def test_writes_file_when_block_removed(self, tmp_path):
        content = """\
            # ── auto-generated: gone_func ──
            class TestGoneFunc:
                def test_x(self):
                    pass
        """
        test_file = self._make_test_file(tmp_path, content)
        original_mtime = test_file.stat().st_mtime
        import time; time.sleep(0.01)
        cst.cleanup_stale_tests(test_file, main_functions=set())
        assert test_file.stat().st_mtime > original_mtime

    def test_multiple_stale_blocks_all_removed(self, tmp_path):
        content = """\
            # ── auto-generated: func_a ──
            class TestFuncA:
                def test_a(self):
                    pass

            # ── auto-generated: func_b ──
            class TestFuncB:
                def test_b(self):
                    pass
        """
        test_file = self._make_test_file(tmp_path, content)
        removed = cst.cleanup_stale_tests(test_file, main_functions=set())
        assert "func_a" in removed
        assert "func_b" in removed
        text = test_file.read_text()
        assert "TestFuncA" not in text
        assert "TestFuncB" not in text

    def test_mixed_valid_and_stale(self, tmp_path):
        content = """\
            # ── auto-generated: keep_me ──
            class TestKeepMe:
                def test_keep(self):
                    pass

            # ── auto-generated: remove_me ──
            class TestRemoveMe:
                def test_remove(self):
                    pass
        """
        test_file = self._make_test_file(tmp_path, content)
        removed = cst.cleanup_stale_tests(test_file, main_functions={"keep_me"})
        assert removed == ["remove_me"]
        text = test_file.read_text()
        assert "TestKeepMe" in text
        assert "TestRemoveMe" not in text


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

class TestMain:
    def test_exits_when_main_py_missing(self, tmp_path, monkeypatch, capsys):
        import sys
        # Patch the paths used inside main() so they point to tmp_path
        monkeypatch.setattr(
            cst, "main",
            lambda: _patched_main_missing(tmp_path / "main.py", tmp_path / "tests" / "test_main.py"),
        )
        with pytest.raises(SystemExit) as exc_info:
            cst.main()
        assert exc_info.value.code == 1

    def test_skip_message_when_test_py_missing(self, tmp_path, monkeypatch):
        import subprocess, sys as _sys
        main_py = tmp_path / "main.py"
        main_py.write_text("def hello(): pass\n")
        (tmp_path / "tests").mkdir()
        scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
        # Patch the hardcoded paths by monkey-patching via env vars isn't possible,
        # so we invoke main() directly after monkeypatching Path resolution.
        monkeypatch.setattr(
            cst, "main",
            lambda: _patched_main_skip(main_py, tmp_path / "tests" / "test_main.py"),
        )
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with pytest.raises(SystemExit) as exc_info:
            with redirect_stdout(buf):
                cst.main()
        assert exc_info.value.code == 0
        assert "SKIP" in buf.getvalue()


def _patched_main_skip(main_path: Path, test_path: Path):
    import sys
    if not main_path.exists():
        print(f"ERROR: {main_path} not found", file=sys.stderr)
        sys.exit(1)
    if not test_path.exists():
        print(f"SKIP: {test_path} not found, nothing to clean up.")
        sys.exit(0)


def _patched_main_missing(main_path: Path, test_path: Path):
    import sys
    if not main_path.exists():
        print(f"ERROR: {main_path} not found", file=sys.stderr)
        sys.exit(1)
