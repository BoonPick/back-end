"""
cleanup_stale_tests.py 자동 생성 테스트
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ── auto-generated: get_main_functions ──────────────────────────────────
```python
class TestGetMainFunctions:
    """Tests for get_main_functions()."""

    def test_single_function(self, tmp_path):
        """Test extracting a single top-level function."""
        main_file = tmp_path / "main.py"
        main_file.write_text("def hello():\n    pass\n", encoding="utf-8")
        result = get_main_functions(main_file)
        assert result == {"hello"}

    def test_multiple_functions(self, tmp_path):
        """Test extracting multiple top-level functions."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            "def foo():\n    pass\n\ndef bar():\n    pass\n\ndef baz():\n    pass\n",
            encoding="utf-8",
        )
        result = get_main_functions(main_file)
        assert result == {"foo", "bar", "baz"}

    def test_async_function(self, tmp_path):
        """Test extracting async top-level functions."""
        main_file = tmp_path / "main.py"
        main_file.write_text("async def async_handler():\n    pass\n", encoding="utf-8")
        result = get_main_functions(main_file)
        assert result == {"async_handler"}

    def test_mixed_sync_and_async(self, tmp_path):
        """Test extracting both sync and async functions."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            "def sync_func():\n    pass\n\nasync def async_func():\n    pass\n",
            encoding="utf-8",
        )
        result = get_main_functions(main_file)
        assert result == {"sync_func", "async_func"}

    def test_empty_file(self, tmp_path):
        """Test with an empty Python file returns empty set."""
        main_file = tmp_path / "main.py"
        main_file.write_text("", encoding="utf-8")
        result = get_main_functions(main_file)
        assert result == set()

    def test_no_functions_only_variables(self, tmp_path):
        """Test file with only variable assignments returns empty set."""
        main_file = tmp_path / "main.py"
        main_file.write_text("x = 1\ny = 'hello'\nz = [1, 2, 3]\n", encoding="utf-8")
        result = get_main_functions(main_file)
        assert result == set()

    def test_nested_functions_are_included(self, tmp_path):
        """Test that nested (inner) functions are also captured by ast.walk."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            "def outer():\n    def inner():\n        pass\n    pass\n",
            encoding="utf-8",
        )
        result = get_main_functions(main_file)
        # ast.walk traverses all nodes, so nested functions are included
        assert "outer" in result
        assert "inner" in result

    def test_class_methods_are_included(self, tmp_path):
        """Test that methods inside classes are found by ast.walk."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            "class MyClass:\n    def method(self):\n        pass\n",
            encoding="utf-8",
        )
        result = get_main_functions(main_file)
        assert "method" in result

    def test_file_with_imports_and_functions(self, tmp_path):
        """Test file containing imports alongside function definitions."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            "import os\nimport sys\n\ndef process():\n    pass\n\ndef run():\n    pass\n",
            encoding="utf-8",
        )
        result = get_main_functions(main_file)
        assert result == {"process", "run"}

    def test_file_with_decorators(self, tmp_path):
        """Test functions with decorators are correctly identified."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            "def decorator(f):\n    return f\n\n@decorator\ndef decorated():\n    pass\n",
            encoding="utf-8",
        )
        result = get_main_functions(main_file)
        assert "decorator" in result
        assert "decorated" in result

    def test_file_with_syntax_error_raises(self, tmp_path):
        """Test that a file with invalid Python syntax raises SyntaxError."""
        main_file = tmp_path / "main.py"
        main_file.write_text("def broken(\n", encoding="utf-8")
        with pytest.raises(SyntaxError):
            get_main_functions(main_file)

    def test_nonexistent_file_raises(self, tmp_path):
        """Test that a nonexistent file raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.py"
        with pytest.raises(FileNotFoundError):
            get_main_functions(nonexistent)

    def test_returns_set_type(self, tmp_path):
        """Test that the return type is always a set."""
        main_file = tmp_path / "main.py"
        main_file.write_text("def a():\n    pass\n", encoding="utf-8")
        result = get_main_functions(main_file)
        assert isinstance(result, set)

    def test_duplicate_function_names(self, tmp_path):
        """Test that duplicate function names result in a single entry (set behavior)."""
        main_file = tmp_path / "main.py"
        main_file.write_text(
            "def dup():\n    pass\n\ndef dup():\n    pass\n",
            encoding="utf-8",
        )
        result = get_main_functions(main_file)
        assert result == {"dup"}

    def test_lambda_not_included(self, tmp_path):
        """Test that lambda expressions are not included (they are not FunctionDef)."""
        main_file = tmp_path / "main.py"
        main_file.write_text("my_lambda = lambda x: x + 1\n", encoding="utf-8")
        result = get_main_functions(main_file)
        assert result == set()

    def test_utf8_function_names(self, tmp_path):
        """Test function names with unicode characters."""
        main_file = tmp_path / "main.py"
        main_file.write_text("def 함수():\n    pass\n", encoding="utf-8")
        result = get_main_functions(main_file)
        assert result == {"함수"}

    def test_file_with_only_comments(self, tmp_path):
        """Test file containing only comments returns empty set."""
        main_file = tmp_path / "main.py"
        main_file.write_text("# This is a comment\n# Another comment\n", encoding="utf-8")
        result = get_main_functions(main_file)
        assert result == set()

    def test_complex_file_structure(self, tmp_path):
        """Test a more complex file with classes, functions, async, and nesting."""
        main_file = tmp_path / "main.py"
        content = (
            "import os\n"
            "\n"
            "CONST = 42\n"
            "\n"
            "def top_func():\n"
            "    pass\n"
            "\n"
            "async def top_async():\n"
            "    pass\n"
            "\n"
            "class Service:\n"
            "    def serve(self):\n"
            "        async def _inner_async():\n"
            "            pass\n"
            "        pass\n"
        )
        main_file.write_text(content, encoding="utf-8")


# ── auto-generated: cleanup_stale_tests ──────────────────────────────────
```python
class TestCleanupStaleTests:
    """Tests for cleanup_stale_tests function."""

    def test_remove_single_stale_function(self, tmp_path):
        """Test that a single stale test block is removed when function no longer exists."""
        test_file = tmp_path / "test_main.py"
        content = (
            "# ── auto-generated: old_func ──\n"
            "class TestOldFunc:\n"
            "    def test_something(self):\n"
            "        pass\n"
        )
        test_file.write_text(content, encoding="utf-8")
        result = cleanup_stale_tests(test_file, set())
        assert result == ["old_func"]
        assert test_file.read_text(encoding="utf-8") == ""

    def test_keep_existing_function(self, tmp_path):
        """Test that test blocks for functions still in main are kept."""
        test_file = tmp_path / "test_main.py"
        content = (
            "# ── auto-generated: my_func ──\n"
            "class TestMyFunc:\n"
            "    def test_it(self):\n"
            "        pass\n"
        )
        test_file.write_text(content, encoding="utf-8")
        result = cleanup_stale_tests(test_file, {"my_func"})
        assert result == []
        assert test_file.read_text(encoding="utf-8") == content

    def test_remove_stale_keep_existing(self, tmp_path):
        """Test mixed scenario: remove stale block but keep existing one."""
        test_file = tmp_path / "test_main.py"
        content = (
            "# ── auto-generated: stale_func ──\n"
            "class TestStaleFunc:\n"
            "    def test_a(self):\n"
            "        pass\n"
            "# ── auto-generated: alive_func ──\n"
            "class TestAliveFunc:\n"
            "    def test_b(self):\n"
            "        pass\n"
        )
        test_file.write_text(content, encoding="utf-8")
        result = cleanup_stale_tests(test_file, {"alive_func"})
        assert result == ["stale_func"]
        remaining = test_file.read_text(encoding="utf-8")
        assert "stale_func" not in remaining
        assert "TestAliveFunc" in remaining
        assert "alive_func" in remaining

    def test_no_markers_returns_empty(self, tmp_path):
        """Test file with no auto-generated markers returns empty list."""
        test_file = tmp_path / "test_main.py"
        content = (
            "class TestManual:\n"
            "    def test_manual(self):\n"
            "        assert True\n"
        )
        test_file.write_text(content, encoding="utf-8")
        result = cleanup_stale_tests(test_file, set())
        assert result == []
        assert test_file.read_text(encoding="utf-8") == content

    def test_empty_file(self, tmp_path):
        """Test with an empty test file."""
        test_file = tmp_path / "test_main.py"
        test_file.write_text("", encoding="utf-8")
        result = cleanup_stale_tests(test_file, {"some_func"})
        assert result == []

    def test_marker_with_blank_lines_before_class(self, tmp_path):
        """Test that blank lines between marker and class are handled correctly."""
        test_file = tmp_path / "test_main.py"
        content = (
            "# ── auto-generated: gone_func ──\n"
            "\n"
            "\n"
            "class TestGoneFunc:\n"
            "    def test_x(self):\n"
            "        pass\n"
        )
        test_file.write_text(content, encoding="utf-8")
        result = cleanup_stale_tests(test_file, set())
        assert result == ["gone_func"]
        assert "TestGoneFunc" not in test_file.read_text(encoding="utf-8")

    def test_multiple_stale_functions_removed(self, tmp_path):
        """Test that multiple stale test blocks are all removed."""
        test_file = tmp_path / "test_main.py"
        content = (
            "# ── auto-generated: func_a ──\n"
            "class TestFuncA:\n"
            "    def test_a(self):\n"
            "        pass\n"
            "# ── auto-generated: func_b ──\n"
            "class TestFuncB:\n"
            "    def test_b(self):\n"
            "        pass\n"
            "# ── auto-generated: func_c ──\n"
            "class TestFuncC:\n"
            "    def test_c(self):\n"
            "        pass\n"
        )
        test_file.write_text(content, encoding="utf-8")
        result = cleanup_stale_tests(test_file, set())
        assert sorted(result) == ["func_a", "func_b", "func_c"]
        assert test_file.read_text(encoding="utf-8") == ""

    def test_file_not_written_when_nothing_removed(self, tmp_path):
        """Test that the file is not rewritten when no blocks are removed."""
        test_file = tmp_path / "test_main.py"
        content = (
            "# ── auto-generated: keeper ──\n"
            "class TestKeeper:\n"
            "    def test_keep(self):\n"
            "        pass\n"
        )
        test_file.write_text(content, encoding="utf-8")
        original_mtime = test_file.stat().st_mtime_ns

        import time
        time.sleep(0.01)

        result = cleanup_stale_tests(test_file, {"keeper"})
        assert result == []
        # File should not have been rewritten
        assert test_file.stat().st_mtime_ns == original_mtime

    def test_non_auto_generated_content_preserved(self, tmp_path):
        """Test that lines without markers are preserved completely."""
        test_file = tmp_path / "test_main.py"
        content = (
            "import pytest\n"
            "\n"
            "# Manual test\n"
            "class TestManual:\n"
            "    def test_manual(self):\n"
            "        assert 1 == 1\n"
            "\n"
            "# ── auto-generated: dead_func ──\n"
            "class TestDeadFunc:\n"
            "    def test_dead(self):\n"
            "        pass\n"
        )
        test_file.write_text(content, encoding="utf-8")
        result = cleanup_stale_tests(test_file, set())
        assert result == ["dead_func"]
        remaining = test_file.read_text(encoding="utf-8")
        assert "import pytest" in remaining
        assert "TestManual" in remaining
        assert "assert 1 == 1" in remaining
        assert "TestDeadFunc" not in remaining

    def test_stale_block_with_multiline_methods(self, tmp_path):
        """Test removal of a block with multiple multi-line test methods."""
        test_file = tmp_path / "test_main.py"
        content = (
            "# ── auto-generated: complex_func ──\n"
            "class TestComplexFunc:\n"
            "    def test_case_one(self):\n"
            "        x = 1\n"
            "        y = 2\n"
            "        assert x + y == 3\n"
            "\n"
            "    def test_case_two(self):\n"
            "        data = [1, 2, 3]\n"
            "        assert


# ── auto-generated: main ──────────────────────────────────
```python
class TestMain:
    """Tests for the main() function."""

    def test_main_missing_main_py(self, tmp_path, monkeypatch):
        """Test that main exits with error when main.py does not exist."""
        # Create directory structure: tmp_path/scripts/cleanup_stale_tests.py
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "cleanup_stale_tests.py"
        fake_script.write_text("", encoding="utf-8")

        # base = fake_script.parent.parent = tmp_path
        # main_py = tmp_path / "main.py" -> does not exist
        # We need to patch Path(__file__) resolution
        import cleanup_stale_tests as module

        monkeypatch.setattr(module, "__file__", str(fake_script))

        # Ensure main.py does NOT exist, but tests dir might
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        test_main_file = tests_dir / "test_main.py"
        test_main_file.write_text("", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            module.main()
        assert exc_info.value.code == 1

    def test_main_missing_test_py(self, tmp_path, monkeypatch):
        """Test that main exits with error when test_main.py does not exist."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "cleanup_stale_tests.py"
        fake_script.write_text("", encoding="utf-8")

        import cleanup_stale_tests as module

        monkeypatch.setattr(module, "__file__", str(fake_script))

        # Create main.py but NOT tests/test_main.py
        main_py = tmp_path / "main.py"
        main_py.write_text("def foo(): pass\n", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            module.main()
        assert exc_info.value.code == 1

    def test_main_missing_main_py_stderr_message(self, tmp_path, monkeypatch, capsys):
        """Test that the correct error message is printed to stderr when main.py is missing."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "cleanup_stale_tests.py"
        fake_script.write_text("", encoding="utf-8")

        import cleanup_stale_tests as module

        monkeypatch.setattr(module, "__file__", str(fake_script))

        with pytest.raises(SystemExit):
            module.main()

        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_main_no_stale_blocks(self, tmp_path, monkeypatch, capsys):
        """Test main prints 'No stale test blocks found.' when nothing is removed."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "cleanup_stale_tests.py"
        fake_script.write_text("", encoding="utf-8")

        import cleanup_stale_tests as module

        monkeypatch.setattr(module, "__file__", str(fake_script))

        # Create main.py with a function
        main_py = tmp_path / "main.py"
        main_py.write_text("def my_func():\n    pass\n", encoding="utf-8")

        # Create test file with matching auto-generated block
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_py = tests_dir / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: my_func ──\n"
            "class TestMyFunc:\n"
            "    def test_it(self):\n"
            "        pass\n",
            encoding="utf-8",
        )

        module.main()

        captured = capsys.readouterr()
        assert "No stale test blocks found." in captured.out

    def test_main_with_stale_blocks(self, tmp_path, monkeypatch, capsys):
        """Test main prints removed block names when stale blocks exist."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "cleanup_stale_tests.py"
        fake_script.write_text("", encoding="utf-8")

        import cleanup_stale_tests as module

        monkeypatch.setattr(module, "__file__", str(fake_script))

        # Create main.py with NO functions
        main_py = tmp_path / "main.py"
        main_py.write_text("# empty\n", encoding="utf-8")

        # Create test file with an auto-generated block that is now stale
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_py = tests_dir / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: old_func ──\n"
            "class TestOldFunc:\n"
            "    def test_old(self):\n"
            "        pass\n",
            encoding="utf-8",
        )

        module.main()

        captured = capsys.readouterr()
        assert "Removed stale test blocks" in captured.out
        assert "old_func" in captured.out

    def test_main_with_multiple_stale_blocks(self, tmp_path, monkeypatch, capsys):
        """Test main correctly reports multiple stale block names."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "cleanup_stale_tests.py"
        fake_script.write_text("", encoding="utf-8")

        import cleanup_stale_tests as module

        monkeypatch.setattr(module, "__file__", str(fake_script))

        # main.py has only func_keep
        main_py = tmp_path / "main.py"
        main_py.write_text("def func_keep():\n    pass\n", encoding="utf-8")

        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        test_py = tests_dir / "test_main.py"
        test_py.write_text(
            "# ── auto-generated: func_keep ──\n"
            "class TestFuncKeep:\n"
            "    def test_keep(self):\n"
            "        pass\n"
            "# ── auto-generated: stale_one ──\n"
            "class TestStaleOne:\n"
            "    def test_one(self):\n"
            "        pass\n"
            "# ── auto-generated: stale_two ──\n"
            "class TestStaleTwo:\n"
            "    def test_two(self):\n"
            "        pass\n",
            encoding="utf-8",
        )

        module.main()

        captured = capsys.readouterr()
        assert "Removed stale test blocks" in captured.out
        assert "stale_one" in captured.out
        assert "stale_two" in captured.out

    def test_main_uses_get_main_functions_result(self, tmp_path, monkeypatch):
        """Test that main correctly passes get_main_functions output to cleanup_stale_tests."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        fake_script = scripts_dir / "cleanup_stale_tests.py"
        fake_script.write_text("", encoding="utf-8")

        import cleanup_stale_tests as module

        monkeypatch.setattr(module, "__file__", str(fake_script))

        main_py =
