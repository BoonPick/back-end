#!/usr/bin/env python3
"""
Remove auto-generated test blocks whose target function no longer exists in main.py.

Auto-generated test blocks are identified by the comment marker:
    # ── auto-generated: function_name ──

Run from the fastapi-app directory:
    python scripts/cleanup_stale_tests.py
"""

import ast
import re
import sys
from pathlib import Path


def get_main_functions(main_path: Path) -> set:
    """Return names of all top-level functions defined in main.py."""
    source = main_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and isinstance(getattr(node, "col_offset", -1), int)
    }


def cleanup_stale_tests(test_path: Path, main_functions: set) -> list:
    """
    Remove test class blocks tagged with auto-generated markers for functions
    that no longer exist in main.py.

    Returns list of removed function names.
    """
    lines = test_path.read_text(encoding="utf-8").splitlines(keepends=True)
    result = []
    removed = []
    i = 0

    while i < len(lines):
        # Look for the auto-generated marker
        marker = re.match(
            r"^# ── auto-generated: (\w+) ──", lines[i].strip()
        )
        if marker:
            func_name = marker.group(1)
            block_start = i

            # Advance past consecutive marker / blank lines
            j = i
            while j < len(lines) and (
                re.match(r"^# ── auto-generated:", lines[j].strip())
                or lines[j].strip() == ""
            ):
                j += 1

            # The next non-blank, non-marker line should be a class definition
            if j < len(lines) and lines[j].startswith("class Test"):
                if func_name not in main_functions:
                    # Find end of this block: next class-level line or next marker
                    k = j + 1
                    while k < len(lines):
                        if lines[k].startswith("class ") or re.match(
                            r"^# ── auto-generated:", lines[k].strip()
                        ):
                            break
                        k += 1
                    removed.append(func_name)
                    i = k
                    continue
                # Function still exists — keep everything up to the class end
            # Fall through: keep this line as-is

        result.append(lines[i])
        i += 1

    if removed:
        test_path.write_text("".join(result), encoding="utf-8")

    return removed


def main():
    base = Path(__file__).resolve().parent.parent  # fastapi-app/
    main_py = base / "main.py"
    test_py = base / "tests" / "test_main.py"

    if not main_py.exists():
        print(f"ERROR: {main_py} not found", file=sys.stderr)
        sys.exit(1)
    if not test_py.exists():
        print(f"ERROR: {test_py} not found", file=sys.stderr)
        sys.exit(1)

    main_funcs = get_main_functions(main_py)
    removed = cleanup_stale_tests(test_py, main_funcs)

    if removed:
        print(f"Removed stale test blocks: {', '.join(removed)}")
    else:
        print("No stale test blocks found.")


if __name__ == "__main__":
    main()
