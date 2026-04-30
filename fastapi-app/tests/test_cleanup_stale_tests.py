import textwrap
from pathlib import Path

import pytest

from scripts.cleanup_stale_tests import cleanup_stale_tests, get_main_functions


def write_py(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(textwrap.dedent(src))
    return p


class TestGetMainFunctions:
    def test_returns_sync_function_names(self, tmp_path):
        p = write_py(tmp_path, "main.py", """
            def foo():
                pass

            def bar():
                pass
        """)
        result = get_main_functions(p)
        assert "foo" in result
        assert "bar" in result

    def test_returns_async_function_names(self, tmp_path):
        p = write_py(tmp_path, "main.py", """
            async def async_fn():
                pass
        """)
        result = get_main_functions(p)
        assert "async_fn" in result

    def test_includes_class_methods(self, tmp_path):
        p = write_py(tmp_path, "main.py", """
            class MyClass:
                def method(self):
                    pass
        """)
        result = get_main_functions(p)
        assert "method" in result

    def test_empty_file_returns_empty_set(self, tmp_path):
        p = write_py(tmp_path, "main.py", "")
        assert get_main_functions(p) == set()

    def test_returns_set_not_list(self, tmp_path):
        p = write_py(tmp_path, "main.py", "def fn(): pass\n")
        result = get_main_functions(p)
        assert isinstance(result, set)


class TestCleanupStaleTests:
    def test_removes_block_for_deleted_function(self, tmp_path):
        test_py = write_py(tmp_path, "test_main.py", """\
            # ── auto-generated: deleted_func ──

            class TestDeletedFunc:
                def test_something(self):
                    pass
        """)
        removed = cleanup_stale_tests(test_py, {"existing_func"})
        assert "deleted_func" in removed
        assert "TestDeletedFunc" not in test_py.read_text()

    def test_keeps_block_for_existing_function(self, tmp_path):
        test_py = write_py(tmp_path, "test_main.py", """\
            # ── auto-generated: keep_me ──

            class TestKeepMe:
                def test_it(self):
                    assert True
        """)
        removed = cleanup_stale_tests(test_py, {"keep_me"})
        assert "keep_me" not in removed
        assert "TestKeepMe" in test_py.read_text()

    def test_returns_empty_list_when_nothing_removed(self, tmp_path):
        test_py = write_py(tmp_path, "test_main.py", """\
            # ── auto-generated: present ──

            class TestPresent:
                def test_x(self):
                    pass
        """)
        removed = cleanup_stale_tests(test_py, {"present"})
        assert removed == []

    def test_file_unchanged_when_no_markers(self, tmp_path):
        original = "def test_manual():\n    assert True\n"
        test_py = tmp_path / "test_main.py"
        test_py.write_text(original)
        removed = cleanup_stale_tests(test_py, set())
        assert removed == []
        assert test_py.read_text() == original

    def test_removes_multiple_stale_blocks(self, tmp_path):
        test_py = write_py(tmp_path, "test_main.py", """\
            # ── auto-generated: gone_a ──

            class TestGoneA:
                def test_a(self):
                    pass

            # ── auto-generated: gone_b ──

            class TestGoneB:
                def test_b(self):
                    pass
        """)
        removed = cleanup_stale_tests(test_py, set())
        assert "gone_a" in removed
        assert "gone_b" in removed
        content = test_py.read_text()
        assert "TestGoneA" not in content
        assert "TestGoneB" not in content

    def test_selectively_removes_only_stale(self, tmp_path):
        test_py = write_py(tmp_path, "test_main.py", """\
            # ── auto-generated: stale_func ──

            class TestStaleFunc:
                def test_s(self):
                    pass

            # ── auto-generated: live_func ──

            class TestLiveFunc:
                def test_l(self):
                    pass
        """)
        removed = cleanup_stale_tests(test_py, {"live_func"})
        assert removed == ["stale_func"]
        content = test_py.read_text()
        assert "TestStaleFunc" not in content
        assert "TestLiveFunc" in content

    def test_does_not_write_file_when_nothing_removed(self, tmp_path):
        original = "# no markers\ndef test_x(): pass\n"
        test_py = tmp_path / "test_main.py"
        test_py.write_text(original)
        mtime_before = test_py.stat().st_mtime
        cleanup_stale_tests(test_py, set())
        assert test_py.stat().st_mtime == mtime_before
