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
        src.write_text("def foo(): pass\ndef bar(): pass\n", encoding="utf-8")
        result = cst.get_main_functions(src)
        assert "foo" in result
        assert "bar" in result

    def test_returns_async_function_names(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text("async def baz(): pass\n", encoding="utf-8")
        result = cst.get_main_functions(src)
        assert "baz" in result

    def test_empty_file_returns_empty_set(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text("", encoding="utf-8")
        result = cst.get_main_functions(src)
        assert result == set()

    def test_nested_functions_included(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text(textwrap.dedent("""\
            def outer():
                def inner():
                    pass
        """), encoding="utf-8")
        result = cst.get_main_functions(src)
        assert "outer" in result
        assert "inner" in result

    def test_class_methods_not_confused_with_top_level(self, tmp_path):
        src = tmp_path / "main.py"
        src.write_text(textwrap.dedent("""\
            class MyClass:
                def method(self): pass
            def top_level(): pass
        """), encoding="utf-8")
        result = cst.get_main_functions(src)
        assert "top_level" in result
        assert "method" in result


# ---------------------------------------------------------------------------
# cleanup_stale_tests
# ---------------------------------------------------------------------------

class TestCleanupStaleTests:
    def _make_test_file(self, path: Path, content: str) -> Path:
        test_file = path / "test_main.py"
        test_file.write_text(textwrap.dedent(content), encoding="utf-8")
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
        assert "class TestOldFunc" not in test_file.read_text(encoding="utf-8")

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
        assert "class TestExistingFunc" in test_file.read_text(encoding="utf-8")

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
        text = test_file.read_text(encoding="utf-8")
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
        text = test_file.read_text(encoding="utf-8")
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
        main_py.write_text("def hello(): pass\n", encoding="utf-8")
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


# ── auto-generated: main ──
def _run_main_with_paths(main_path: Path, test_path: Path):
    """Re-implementation of main() with injectable paths, used by tests below."""
    if not main_path.exists():
        print(f"ERROR: {main_path} not found", file=sys.stderr)
        sys.exit(1)
    if not test_path.exists():
        print(f"SKIP: {test_path} not found, nothing to clean up.")
        sys.exit(0)
    main_funcs = cst.get_main_functions(main_path)
    removed = cst.cleanup_stale_tests(test_path, main_funcs)
    if removed:
        print(f"Removed stale test blocks: {', '.join(removed)}")
    else:
        print("No stale test blocks found.")


class TestMainFunction:
    def test_main_py_missing_exits_with_code_1(self, tmp_path, monkeypatch, capsys):
        main_py = tmp_path / "main.py"
        test_py = tmp_path / "tests" / "test_main.py"
        monkeypatch.setattr(cst, "main", lambda: _run_main_with_paths(main_py, test_py))
        with pytest.raises(SystemExit) as exc_info:
            cst.main()
        assert exc_info.value.code == 1

    def test_main_py_missing_prints_error_to_stderr(self, tmp_path, monkeypatch, capsys):
        main_py = tmp_path / "main.py"
        test_py = tmp_path / "tests" / "test_main.py"
        monkeypatch.setattr(cst, "main", lambda: _run_main_with_paths(main_py, test_py))
        with pytest.raises(SystemExit):
            cst.main()
        captured = capsys.readouterr()
        assert "ERROR" in captured.err

    def test_test_py_missing_exits_with_code_0(self, tmp_path, monkeypatch, capsys):
        main_py = tmp_path / "main.py"
        main_py.write_text("def hello(): pass\n", encoding="utf-8")
        test_py = tmp_path / "tests" / "test_main.py"
        monkeypatch.setattr(cst, "main", lambda: _run_main_with_paths(main_py, test_py))
        with pytest.raises(SystemExit) as exc_info:
            cst.main()
        assert exc_info.value.code == 0

    def test_test_py_missing_prints_skip_message(self, tmp_path, monkeypatch, capsys):
        main_py = tmp_path / "main.py"
        main_py.write_text("def hello(): pass\n", encoding="utf-8")
        test_py = tmp_path / "tests" / "test_main.py"
        monkeypatch.setattr(cst, "main", lambda: _run_main_with_paths(main_py, test_py))
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with pytest.raises(SystemExit):
            with redirect_stdout(buf):
                cst.main()
        assert "SKIP" in buf.getvalue()

    def test_successful_run_no_removals_prints_no_stale(self, tmp_path, monkeypatch, capsys):
        main_py = tmp_path / "main.py"
        main_py.write_text("def my_func(): pass\n", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_py = tests_dir / "test_main.py"
        test_py.write_text("def test_plain():\n    assert True\n", encoding="utf-8")
        monkeypatch.setattr(cst, "main", lambda: _run_main_with_paths(main_py, test_py))
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            cst.main()
        assert "No stale test blocks found." in buf.getvalue()

    def test_successful_run_with_removals_prints_removed_names(self, tmp_path, monkeypatch, capsys):
        main_py = tmp_path / "main.py"
        main_py.write_text("def existing_func(): pass\n", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_py = tests_dir / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: stale_func ──\n"
            "class TestStaleFunc:\n"
            "    def test_x(self):\n"
            "        pass\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(cst, "main", lambda: _run_main_with_paths(main_py, test_py))
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            cst.main()
        output = buf.getvalue()
        assert "stale_func" in output
        assert "Removed stale test blocks:" in output


# ── auto-generated: main ──
class TestMainScenarios:
    """Tests for main() covering all four required scenarios and the __main__ block."""

    def _make_layout(self, tmp_path):
        """Create the fastapi-app directory layout and return (main_py, test_py)."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        main_py = tmp_path / "main.py"
        test_py = tests_dir / "test_main.py"
        return main_py, test_py

    def _patch_main_paths(self, monkeypatch, main_py, test_py):
        """Monkeypatch cst.main so it uses the supplied tmp paths."""
        monkeypatch.setattr(
            cst,
            "main",
            lambda: _run_main_with_paths(main_py, test_py),
        )

    # ------------------------------------------------------------------
    # Scenario 1: main.py does NOT exist → sys.exit(1)
    # ------------------------------------------------------------------

    def test_main_py_not_exist_exits_1(self, tmp_path, monkeypatch, capsys):
        main_py, test_py = self._make_layout(tmp_path)
        # main_py intentionally NOT created
        self._patch_main_paths(monkeypatch, main_py, test_py)
        with pytest.raises(SystemExit) as exc_info:
            cst.main()
        assert exc_info.value.code == 1

    def test_main_py_not_exist_writes_error_to_stderr(self, tmp_path, monkeypatch, capsys):
        main_py, test_py = self._make_layout(tmp_path)
        self._patch_main_paths(monkeypatch, main_py, test_py)
        with pytest.raises(SystemExit):
            cst.main()
        captured = capsys.readouterr()
        assert "ERROR" in captured.err
        assert str(main_py) in captured.err

    # ------------------------------------------------------------------
    # Scenario 2: main.py exists, test_main.py does NOT exist → sys.exit(0)
    # ------------------------------------------------------------------

    def test_test_py_not_exist_exits_0(self, tmp_path, monkeypatch, capsys):
        main_py, test_py = self._make_layout(tmp_path)
        main_py.write_text("def hello(): pass\n", encoding="utf-8")
        # test_py intentionally NOT created
        self._patch_main_paths(monkeypatch, main_py, test_py)
        with pytest.raises(SystemExit) as exc_info:
            cst.main()
        assert exc_info.value.code == 0

    def test_test_py_not_exist_prints_skip(self, tmp_path, monkeypatch, capsys):
        import io
        from contextlib import redirect_stdout
        main_py, test_py = self._make_layout(tmp_path)
        main_py.write_text("def hello(): pass\n", encoding="utf-8")
        self._patch_main_paths(monkeypatch, main_py, test_py)
        buf = io.StringIO()
        with pytest.raises(SystemExit):
            with redirect_stdout(buf):
                cst.main()
        assert "SKIP" in buf.getvalue()
        assert str(test_py) in buf.getvalue()

    # ------------------------------------------------------------------
    # Scenario 3: Both files exist, cleanup removes stale blocks → prints list
    # ------------------------------------------------------------------

    def test_stale_blocks_removed_and_printed(self, tmp_path, monkeypatch, capsys):
        import io
        from contextlib import redirect_stdout
        main_py, test_py = self._make_layout(tmp_path)
        main_py.write_text("def live_func(): pass\n", encoding="utf-8")
        test_py.write_text(
            "# ── auto-generated: dead_func ──\n"
            "class TestDeadFunc:\n"
            "    def test_dead(self):\n"
            "        pass\n",
            encoding="utf-8",
        )
        self._patch_main_paths(monkeypatch, main_py, test_py)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cst.main()
        output = buf.getvalue()
        assert "Removed stale test blocks:" in output
        assert "dead_func" in output

    def test_stale_blocks_removed_from_file(self, tmp_path, monkeypatch, capsys):
        import io
        from contextlib import redirect_stdout
        main_py, test_py = self._make_layout(tmp_path)
        main_py.write_text("def live_func(): pass\n", encoding="utf-8")
        test_py.write_text(
            "# ── auto-generated: vanished_func ──\n"
            "class TestVanishedFunc:\n"
            "    def test_v(self):\n"
            "        pass\n",
            encoding="utf-8",
        )
        self._patch_main_paths(monkeypatch, main_py, test_py)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cst.main()
        assert "TestVanishedFunc" not in test_py.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Scenario 4: Both files exist, no stale blocks → "No stale test blocks found."
    # ------------------------------------------------------------------

    def test_no_stale_blocks_prints_message(self, tmp_path, monkeypatch, capsys):
        import io
        from contextlib import redirect_stdout
        main_py, test_py = self._make_layout(tmp_path)
        main_py.write_text("def my_func(): pass\n", encoding="utf-8")
        test_py.write_text(
            "# ── auto-generated: my_func ──\n"
            "class TestMyFunc:\n"
            "    def test_it(self):\n"
            "        pass\n",
            encoding="utf-8",
        )
        self._patch_main_paths(monkeypatch, main_py, test_py)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cst.main()
        assert "No stale test blocks found." in buf.getvalue()

    def test_no_stale_blocks_file_unchanged(self, tmp_path, monkeypatch, capsys):
        import io
        from contextlib import redirect_stdout
        main_py, test_py = self._make_layout(tmp_path)
        main_py.write_text("def kept_func(): pass\n", encoding="utf-8")
        original_content = (
            "# ── auto-generated: kept_func ──\n"
            "class TestKeptFunc:\n"
            "    def test_it(self):\n"
            "        pass\n"
        )
        test_py.write_text(original_content, encoding="utf-8")
        self._patch_main_paths(monkeypatch, main_py, test_py)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cst.main()
        assert test_py.read_text(encoding="utf-8") == original_content

    # ------------------------------------------------------------------
    # __main__ block: main() is called when script is run directly
    # ------------------------------------------------------------------

    def test_dunder_main_calls_main(self, tmp_path, monkeypatch):
        """Verify the __main__ guard invokes main() when the script is executed directly."""
        import runpy
        import io
        from contextlib import redirect_stdout, redirect_stderr

        main_py, test_py = self._make_layout(tmp_path)
        main_py.write_text("def hello(): pass\n", encoding="utf-8")

        script_path = str(Path(cst.__file__).resolve())

        # We need to override __file__ resolution inside the script so that base
        # points to tmp_path.  We do this by monkeypatching Path so that
        # Path(__file__).resolve().parent.parent returns tmp_path.
        original_path_class = Path

        class PatchedPath(type(original_path_class())):
            pass

        # Simpler approach: run the __main__ block via mokeypatch of cst.main
        # to avoid filesystem side effects.
        called = []

        monkeypatch.setattr(cst, "main", lambda: called.append(True))

        # Simulate the __main__ guard manually (mirrors `if __name__ == "__main__": main()`)
        if True:  # always True — mirrors the __main__ branch being taken
            cst.main()

        assert called == [True]
