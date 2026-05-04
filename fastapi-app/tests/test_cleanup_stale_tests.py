import sys
import types
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# pdfplumber stub so conftest path-insert doesn't fail on import side effects
_mock_pdfplumber = types.ModuleType("pdfplumber")
sys.modules.setdefault("pdfplumber", _mock_pdfplumber)
_mock_pdfviewer = types.ModuleType("pdfviewer")
sys.modules.setdefault("pdfviewer", _mock_pdfviewer)

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from cleanup_stale_tests import get_main_functions, cleanup_stale_tests, main


class TestGetMainFunctions:
    def test_finds_regular_function(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("def foo(): pass\ndef bar(): pass\n")
        result = get_main_functions(f)
        assert "foo" in result
        assert "bar" in result

    def test_finds_async_function(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("async def baz():\n    pass\n")
        result = get_main_functions(f)
        assert "baz" in result

    def test_returns_set_type(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("def foo(): pass\n")
        result = get_main_functions(f)
        assert isinstance(result, set)

    def test_empty_file_returns_empty_set(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("")
        result = get_main_functions(f)
        assert result == set()

    def test_multiple_functions_all_found(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("def a(): pass\ndef b(): pass\nasync def c(): pass\n")
        result = get_main_functions(f)
        assert result >= {"a", "b", "c"}

    def test_class_methods_also_captured(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("class Foo:\n    def method(self): pass\n")
        result = get_main_functions(f)
        assert "method" in result


class TestCleanupStaleTests:
    def test_removes_block_for_missing_function(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: old_func ──\n"
            "class TestOldFunc:\n"
            "    def test_something(self): pass\n",
            encoding="utf-8",
        )
        removed = cleanup_stale_tests(test_py, {"existing_func"})
        assert "old_func" in removed
        remaining = test_py.read_text(encoding="utf-8")
        assert "class TestOldFunc" not in remaining

    def test_keeps_block_for_existing_function(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: live_func ──\n"
            "class TestLiveFunc:\n"
            "    def test_something(self): pass\n",
            encoding="utf-8",
        )
        removed = cleanup_stale_tests(test_py, {"live_func"})
        assert "live_func" not in removed
        remaining = test_py.read_text(encoding="utf-8")
        assert "class TestLiveFunc" in remaining

    def test_returns_empty_list_when_no_markers(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text("def test_manual(): pass\n", encoding="utf-8")
        removed = cleanup_stale_tests(test_py, {"some_func"})
        assert removed == []

    def test_removes_only_stale_keeps_live(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: stale_func ──\n"
            "class TestStaleFunc:\n"
            "    def test_it(self): pass\n"
            "# ── auto-generated: live_func ──\n"
            "class TestLiveFunc:\n"
            "    def test_it(self): pass\n",
            encoding="utf-8",
        )
        removed = cleanup_stale_tests(test_py, {"live_func"})
        assert "stale_func" in removed
        assert "live_func" not in removed
        remaining = test_py.read_text(encoding="utf-8")
        assert "class TestStaleFunc" not in remaining
        assert "class TestLiveFunc" in remaining

    def test_returns_list_type(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text("", encoding="utf-8")
        result = cleanup_stale_tests(test_py, set())
        assert isinstance(result, list)

    def test_file_unchanged_when_nothing_removed(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        content = "def test_manual(): pass\n"
        test_py.write_text(content, encoding="utf-8")
        cleanup_stale_tests(test_py, {"func"})
        assert test_py.read_text(encoding="utf-8") == content

    def test_file_written_when_stale_removed(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: gone ──\n"
            "class TestGone:\n"
            "    pass\n",
            encoding="utf-8",
        )
        cleanup_stale_tests(test_py, set())
        assert "class TestGone" not in test_py.read_text(encoding="utf-8")

    def test_multiple_removed_functions_returned(self, tmp_path):
        test_py = tmp_path / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: alpha ──\n"
            "class TestAlpha:\n"
            "    pass\n"
            "# ── auto-generated: beta ──\n"
            "class TestBeta:\n"
            "    pass\n",
            encoding="utf-8",
        )
        removed = cleanup_stale_tests(test_py, set())
        assert set(removed) == {"alpha", "beta"}


class TestMain:
    def test_exits_with_error_when_main_py_missing(self, tmp_path):
        with patch("cleanup_stale_tests.Path") as MockPath:
            base = MagicMock()
            base.__truediv__ = MagicMock(side_effect=lambda self, other: tmp_path / other)
            MockPath.return_value.resolve.return_value.parent.parent = tmp_path
            with pytest.raises(SystemExit):
                main()

    def test_skips_gracefully_when_test_file_missing(self, tmp_path):
        main_py = tmp_path / "main.py"
        main_py.write_text("def foo(): pass\n")
        with patch("cleanup_stale_tests.Path") as MockPath:
            instance = MagicMock()
            instance.resolve.return_value.parent.parent = tmp_path
            MockPath.return_value = instance
            # test_py doesn't exist — main should print SKIP and exit 0
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
