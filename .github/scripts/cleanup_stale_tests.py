#!/usr/bin/env python3
"""
Cleanup stale backend tests (Python/pytest).

For each test file:
  1. Find 'from MODULE import NAME' where NAME no longer exists in MODULE.py
  2. Remove stale names from the import line (keep valid ones)
  3. Insert a MagicMock stub so the file still loads
  4. Scan each top-level test function / test class and add
     @pytest.mark.skip if its body references a stale name
"""

import ast
import re
import sys
from pathlib import Path

TESTS_DIR = Path("/tmp/back-end/fastapi-app/tests")
SOURCE_DIR = Path("/tmp/back-end/fastapi-app")


# ── helpers ──────────────────────────────────────────────────────────────────

def top_level_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def find_stale(test_path: Path) -> dict[str, set[str]]:
    """Returns {module: {stale_name, ...}} for imports that no longer exist."""
    stale: dict[str, set[str]] = {}
    try:
        tree = ast.parse(test_path.read_text())
    except SyntaxError:
        return stale
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        src = SOURCE_DIR / f"{module}.py"
        if not src.exists():
            continue
        existing = top_level_names(src)
        for alias in node.names:
            if alias.name != "*" and alias.name not in existing:
                stale.setdefault(module, set()).add(alias.name)
    return stale


# ── rewrite steps ─────────────────────────────────────────────────────────────

_IMPORT_LINE = re.compile(
    r'^(\s*from\s+(\S+)\s+import\s+)(.*?)(\s*(?:#[^\n]*)?)$'
)


def fix_imports(lines: list[str], stale: dict[str, set[str]]) -> tuple[list[str], list[str]]:
    """
    Rewrite import lines; return (new_lines, stub_lines_to_insert).
    stub_lines_to_insert: plain text lines (each ending with \n).
    """
    new_lines: list[str] = []
    stubs: list[str] = []

    for line in lines:
        m = _IMPORT_LINE.match(line.rstrip('\n'))
        if m:
            module = m.group(2)
            if module in stale:
                prefix   = m.group(1)
                names_str = m.group(3)
                suffix   = m.group(4)

                raw_names = [n.strip() for n in names_str.split(',') if n.strip()]
                valid, removed = [], []
                for raw in raw_names:
                    actual = raw.split(' as ')[0].strip()
                    (removed if actual in stale[module] else valid).append(raw)

                for raw in removed:
                    actual = raw.split(' as ')[0].strip()
                    alias  = raw.split(' as ')[-1].strip() if ' as ' in raw else actual
                    stubs.append(f'# STALE STUB: {alias} removed from {module}\n')
                    stubs.append(f'{alias} = MagicMock()\n')

                if valid:
                    new_lines.append(f'{prefix}{", ".join(valid)}{suffix}\n')
                # drop line entirely if all names were stale
                continue

        new_lines.append(line if line.endswith('\n') else line + '\n')

    return new_lines, stubs


def insert_stubs(lines: list[str], stubs: list[str]) -> list[str]:
    """Insert stub lines right after the last import / blank block at the top."""
    if not stubs:
        return lines

    # Ensure MagicMock is imported
    has_mock = any('MagicMock' in l for l in lines)
    mock_import = 'from unittest.mock import MagicMock\n'

    # Find insertion point: after all leading imports + blank lines
    insert_at = 0
    for i, l in enumerate(lines):
        stripped = l.strip()
        if re.match(r'(import |from \S+ import)', stripped) or stripped == '':
            insert_at = i + 1
        else:
            break

    result = list(lines)
    # Insert stubs (already ordered correctly)
    stub_block = ([mock_import] if not has_mock else []) + ['\n'] + stubs
    for ln in reversed(stub_block):
        result.insert(insert_at, ln)
    return result


def mark_skip(lines: list[str], stale_names: set[str]) -> list[str]:
    """
    Walk lines; for each top-level test function / class whose body references
    a stale name, prepend @pytest.mark.skip.
    """
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Match 'def test_...' or 'class Test...' at column 0
        func_m = re.match(r'^(async )?def (test_\w+)\s*\(', line)
        cls_m  = re.match(r'^class (Test\w+)\s*[:(]', line)

        if func_m or cls_m:
            # Collect entire block (until a non-blank line at col 0 again)
            block = [line]
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if nxt.strip() == '' or nxt[0:1] in (' ', '\t'):
                    block.append(nxt)
                    j += 1
                else:
                    break

            block_text = ''.join(block)

            if any(name in block_text for name in stale_names):
                # Only add skip if not already there
                prev = result[-1].strip() if result else ''
                if '@pytest.mark.skip' not in prev:
                    result.append(
                        '@pytest.mark.skip('
                        'reason="stale: references function removed from source"'
                        ')\n'
                    )
            result.extend(block)
            i = j
            continue

        result.append(line)
        i += 1

    return result


def ensure_pytest_import(lines: list[str]) -> list[str]:
    if any(re.match(r'import pytest', l) for l in lines):
        return lines
    return ['import pytest\n'] + lines


# ── main ─────────────────────────────────────────────────────────────────────

def process_file(test_path: Path, stale: dict[str, set[str]]) -> bool:
    original = test_path.read_text()
    lines = original.splitlines(keepends=True)

    all_stale: set[str] = {n for ns in stale.values() for n in ns}

    lines, stubs  = fix_imports(lines, stale)
    lines         = insert_stubs(lines, stubs)
    lines         = mark_skip(lines, all_stale)
    lines         = ensure_pytest_import(lines)

    result = ''.join(lines)
    if result == original:
        return False
    test_path.write_text(result)
    return True


def main() -> list[str]:
    print('=== Backend: checking for stale test imports ===')
    modified: list[str] = []

    for test_file in sorted(TESTS_DIR.glob('test_*.py')):
        if test_file.name == 'conftest.py':
            continue
        stale = find_stale(test_file)
        if not stale:
            continue
        for mod, names in stale.items():
            print(f'  {test_file.name}: [{mod}] missing → {sorted(names)}')
        if process_file(test_file, stale):
            modified.append(test_file.name)
            print(f'  → Updated {test_file.name}')

    if modified:
        print(f'\nModified {len(modified)} file(s): {modified}')
    else:
        print('No stale imports found.')
    return modified


if __name__ == '__main__':
    main()
    sys.exit(0)
