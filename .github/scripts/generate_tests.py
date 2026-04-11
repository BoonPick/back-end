#!/usr/bin/env python3
"""
새로 추가/변경된 함수를 감지하여 Claude API로 테스트 코드를 자동 생성/수정합니다.

동작 규칙:
  - 새 .py 파일         → test_name.py 신규 생성
  - 기존 파일 + 새 함수  → 테스트 섹션 append
  - 기존 파일 + 수정 함수 → auto-generated 섹션 교체 (수동 작성 테스트는 건드리지 않음)
  - 변경 없음           → API 호출 없이 종료

실행 위치: 레포 루트 (back-end/)
"""

import ast
import re
import subprocess
import textwrap
from pathlib import Path

import anthropic

FASTAPI_APP_DIR = Path("fastapi-app")
TESTS_DIR = FASTAPI_APP_DIR / "tests"

# auto-generated 섹션 구분자 패턴
SEPARATOR_TEMPLATE = "# ── auto-generated: {name} ──────────────────────────────────"


# ── Git 유틸 ──────────────────────────────────────────────────────

def run_git(args):
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode


def is_first_commit():
    _, rc = run_git(["rev-parse", "HEAD~1"])
    return rc != 0


def get_changed_files():
    """HEAD~1..HEAD 사이에 추가/변경된 소스 Python 파일 목록"""
    if is_first_commit():
        stdout, _ = run_git(["ls-files", "--", "*.py"])
    else:
        stdout, _ = run_git(
            ["diff", "HEAD~1", "HEAD", "--name-only", "--diff-filter=AM"]
        )

    return [
        Path(f) for f in stdout.splitlines()
        if f.endswith(".py")
        and f.startswith("fastapi-app/")
        and "tests" not in Path(f).parts
    ]


def get_old_source(filepath):
    stdout, rc = run_git(["show", f"HEAD~1:{filepath}"])
    return stdout if rc == 0 else None


# ── AST 파싱 ─────────────────────────────────────────────────────

def extract_top_level_functions(source):
    """모듈 최상위 함수 및 클래스 메서드 추출 (중첩 함수 제외)"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    lines = source.splitlines()
    functions = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_make_func_info(node, lines))
        elif isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(_make_func_info(child, lines, class_name=node.name))

    return functions


def _make_func_info(node, lines, class_name=None):
    raw = "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return {
        "name": node.name,
        "source": textwrap.dedent(raw),
        "class_name": class_name,
        "is_new": False,      # get_new_or_changed_functions에서 채워짐
        "old_source": None,   # 수정된 함수의 경우 이전 소스
    }


def get_deleted_functions(filepath):
    """이번 커밋에서 삭제된 함수 이름 목록"""
    old_source = get_old_source(filepath)
    if old_source is None:
        return []
    with open(filepath, encoding="utf-8") as f:
        new_source = f.read()
    new_names = {f["name"] for f in extract_top_level_functions(new_source)}
    old_names = {f["name"] for f in extract_top_level_functions(old_source)}
    return list(old_names - new_names)


def get_new_or_changed_functions(filepath):
    """추가되거나 본문이 바뀐 함수만 반환. is_new / old_source 필드 포함."""
    with open(filepath, encoding="utf-8") as f:
        new_source = f.read()

    new_funcs = {f["name"]: f for f in extract_top_level_functions(new_source)}

    old_source = get_old_source(filepath)
    if old_source is None:
        # 새 파일: 모든 함수가 신규
        for func in new_funcs.values():
            func["is_new"] = True
        return list(new_funcs.values())

    old_funcs = {f["name"]: f for f in extract_top_level_functions(old_source)}

    changed = []
    for name, func in new_funcs.items():
        if name not in old_funcs:
            func["is_new"] = True
            changed.append(func)
        elif old_funcs[name]["source"] != func["source"]:
            func["is_new"] = False
            func["old_source"] = old_funcs[name]["source"]
            changed.append(func)

    return changed


def get_imports(filepath):
    """파일의 import 구문만 추출"""
    with open(filepath, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    lines = source.splitlines()
    import_lines = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.extend(lines[node.lineno - 1 : node.end_lineno])
    return "\n".join(import_lines)


# ── 테스트 파일 관리 ──────────────────────────────────────────────

def test_file_for(source_file):
    return TESTS_DIR / f"test_{source_file.stem}.py"


def read_existing_tests(test_file):
    return test_file.read_text(encoding="utf-8") if test_file.exists() else ""


def has_auto_generated_section(existing_tests, func_name):
    """Claude가 자동 생성한 섹션이 있는지 확인"""
    return SEPARATOR_TEMPLATE.format(name=func_name) in existing_tests


def has_any_test(existing_tests, func_name):
    """자동/수동 여부에 관계없이 테스트가 존재하는지 확인"""
    return (
        f"def test_{func_name}" in existing_tests
        or f"class Test{func_name.capitalize()}" in existing_tests
        or has_auto_generated_section(existing_tests, func_name)
    )


def extract_auto_generated_section(existing_tests, func_name):
    """기존 auto-generated 섹션 텍스트 추출 (Claude에게 참고용으로 전달)"""
    separator = SEPARATOR_TEMPLATE.format(name=func_name)
    start = existing_tests.find(separator)
    if start == -1:
        return ""

    # 다음 auto-generated 섹션 시작 또는 EOF
    next_sep = existing_tests.find("# ── auto-generated:", start + len(separator))
    if next_sep == -1:
        return existing_tests[start:]
    return existing_tests[start:next_sep].rstrip()


def append_tests(test_file, new_test_code, func_name):
    """테스트 파일에 새 섹션 추가 (없으면 파일 신규 생성)"""
    separator = f"\n\n{SEPARATOR_TEMPLATE.format(name=func_name)}\n"

    if test_file.exists():
        with open(test_file, "a", encoding="utf-8") as f:
            f.write(separator)
            f.write(new_test_code.rstrip())
            f.write("\n")
    else:
        stem = test_file.stem.replace("test_", "")
        header = (
            f'"""\n{stem}.py 자동 생성 테스트\n"""\n\n'
            "import pytest\n"
            "from unittest.mock import MagicMock, AsyncMock, patch\n"
        )
        test_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(header)
            f.write(separator)
            f.write(new_test_code.rstrip())
            f.write("\n")


def remove_auto_generated_section(test_file, func_name):
    """auto-generated 섹션 삭제 (함수가 소스에서 제거된 경우)"""
    if not test_file.exists():
        return
    content = test_file.read_text(encoding="utf-8")
    separator_line = SEPARATOR_TEMPLATE.format(name=func_name)
    if separator_line not in content:
        return
    pattern = (
        rf"\n\n{re.escape(separator_line)}\n"
        rf".*?"
        rf"(?=\n\n# ── auto-generated:|\Z)"
    )
    new_content = re.sub(pattern, "", content, flags=re.DOTALL)
    test_file.write_text(new_content, encoding="utf-8")


def replace_auto_generated_section(test_file, new_test_code, func_name):
    """기존 auto-generated 섹션을 새 코드로 교체"""
    content = test_file.read_text(encoding="utf-8")
    separator_line = SEPARATOR_TEMPLATE.format(name=func_name)

    # 섹션 시작 ~ 다음 섹션 시작(또는 EOF) 범위를 교체
    pattern = (
        rf"(\n\n{re.escape(separator_line)}\n)"  # 구분자
        rf"(.*?)"                                 # 섹션 내용
        rf"(?=\n\n# ── auto-generated:|\Z)"       # 다음 섹션 또는 EOF
    )
    replacement = (
        f"\n\n{separator_line}\n"
        + new_test_code.rstrip()
        + "\n"
    )
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    test_file.write_text(new_content, encoding="utf-8")


# ── Claude API 호출 ───────────────────────────────────────────────

def _is_valid_python(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _strip_markdown_artifacts(code: str) -> str:
    """코드 앞뒤에 남아있는 마크다운 잔여물 제거."""
    # 앞쪽 ```python / ``` 제거
    code = re.sub(r"^```(?:python|py)?\s*\n?", "", code, flags=re.IGNORECASE)
    # 뒤쪽 ``` 제거
    code = re.sub(r"\n?```\s*$", "", code)
    return code.strip()


def _strip_leading_prose(code: str) -> str:
    """Python 코드가 시작되기 전의 설명 줄(한국어 등) 제거."""
    lines = code.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # import / class / def / @ / # 으로 시작하거나 빈 줄이면 코드 시작
        if not stripped:
            continue
        if re.match(r"^(import |from |class |def |@|#)", stripped):
            return "\n".join(lines[i:])
    return code


def extract_code_block(text: str) -> str:
    """
    Claude 응답에서 Python 코드 블록을 추출한다.

    시도 순서:
    1. 가장 긴 ```python...``` 블록 (docstring 내 중첩 backtick 대응: 마지막 ``` 기준)
    2. 응답 전체에서 마크다운 아티팩트만 제거
    3. 위 둘 다 파싱 실패 시 앞쪽 설명 줄을 제거하고 재시도
    """
    candidates = []

    # 전략 1: ```python ... ``` 블록 전부 수집, 가장 긴 것 우선
    all_blocks = re.findall(
        r"```(?:python|py)?\s*\n(.*?)\n```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if all_blocks:
        candidates.append(max(all_blocks, key=len).strip())

    # 전략 2: 전체 텍스트에서 마크다운 아티팩트 제거
    candidates.append(_strip_markdown_artifacts(text))

    # 전략 3: 원본 그대로
    candidates.append(text.strip())

    # 파싱 가능한 첫 번째 후보 반환
    for code in candidates:
        if _is_valid_python(code):
            return code
        # 앞쪽 설명 줄 제거 후 재시도
        cleaned = _strip_leading_prose(code)
        if cleaned != code and _is_valid_python(cleaned):
            return cleaned

    # 모두 실패 → 가장 긴 후보 반환 (최선)
    return max(candidates, key=len)


def call_claude_create(func_info, module_imports, existing_tests, source_filename):
    """새 함수에 대한 테스트 생성"""
    client = anthropic.Anthropic()

    context_label = (
        f"클래스 `{func_info['class_name']}`의 메서드"
        if func_info["class_name"] else "최상위 함수"
    )
    existing_snippet = existing_tests[-3000:] if len(existing_tests) > 3000 else existing_tests

    prompt = f"""아래 Python {context_label}에 대한 pytest 테스트 코드를 작성해주세요.

## 소스 파일: {source_filename}

### 모듈 imports:
```python
{module_imports}
```

### 테스트할 함수:
```python
{func_info['source']}
```

### 기존 테스트 파일 (중복 금지):
```python
{existing_snippet}
```

## 규칙:
1. pytest 형식 (TestClass 또는 test_ 함수)
2. DB·HTTP·파일 등 외부 의존성은 `unittest.mock`으로 mock 처리
3. 정상 케이스 + 엣지 케이스 + 예외 케이스 포함
4. 기존 테스트와 절대 중복 금지
5. import 문 포함하지 말 것
6. 반드시 ```python ... ``` 코드 블록으로만 응답

테스트 코드:"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def call_claude_update(func_info, module_imports, existing_section, source_filename):
    """수정된 함수에 맞게 기존 테스트 업데이트"""
    client = anthropic.Anthropic()

    prompt = f"""아래 Python 함수가 수정되었습니다. 기존 테스트를 변경된 함수에 맞게 업데이트해주세요.

## 소스 파일: {source_filename}

### 수정 전 함수:
```python
{func_info['old_source']}
```

### 수정 후 함수:
```python
{func_info['source']}
```

### 업데이트할 기존 테스트:
```python
{existing_section}
```

## 규칙:
1. 함수 변경사항을 반영하여 테스트를 수정
2. 기존 테스트 구조를 최대한 유지하되, 변경된 동작에 맞게 조정
3. import 문 포함하지 말 것
4. 반드시 ```python ... ``` 코드 블록으로만 응답

업데이트된 테스트 코드:"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    changed_files = get_changed_files()
    if not changed_files:
        print("변경된 Python 파일 없음. 종료.")
        return

    generated_count = 0
    updated_count = 0
    removed_count = 0

    for source_file in changed_files:
        print(f"\n파일 분석 중: {source_file}")

        changed_funcs = get_new_or_changed_functions(source_file)
        if not changed_funcs:
            print("  변경된 함수 없음, 건너뜀")
            continue

        test_file = test_file_for(source_file)
        module_imports = get_imports(source_file)

        for func in changed_funcs:
            name = func["name"]

            # private 함수 건너뜀 (__init__ 은 예외)
            if name.startswith("_") and name != "__init__":
                print(f"  SKIP (private): {name}")
                continue

            existing_tests = read_existing_tests(test_file)

            if has_auto_generated_section(existing_tests, name):
                # 수정된 함수 + auto-generated 테스트 존재 → 교체
                print(f"  업데이트 중: {name}()")
                existing_section = extract_auto_generated_section(existing_tests, name)
                response = call_claude_update(func, module_imports, existing_section, source_file.name)
                test_code = extract_code_block(response)
                if not _is_valid_python(test_code):
                    print(f"  WARN: {name}() 테스트 코드 파싱 실패, 건너뜀")
                    continue
                replace_auto_generated_section(test_file, test_code, name)
                updated_count += 1
                print(f"  완료 (교체) → {test_file}")

            elif has_any_test(existing_tests, name):
                # 수동 작성 테스트 존재 → 건드리지 않음
                print(f"  SKIP (수동 작성 테스트 존재): {name}")

            else:
                # 테스트 없음 → 새로 생성
                print(f"  생성 중: {name}()")
                response = call_claude_create(func, module_imports, existing_tests, source_file.name)
                test_code = extract_code_block(response)
                if not _is_valid_python(test_code):
                    print(f"  WARN: {name}() 테스트 코드 파싱 실패, 건너뜀")
                    continue
                append_tests(test_file, test_code, name)
                generated_count += 1
                print(f"  완료 (신규) → {test_file}")

        # 삭제된 함수의 auto-generated 섹션 제거
        deleted_funcs = get_deleted_functions(source_file)
        for name in deleted_funcs:
            existing_tests = read_existing_tests(test_file)
            if has_auto_generated_section(existing_tests, name):
                print(f"  삭제 중 (함수 제거됨): {name}()")
                remove_auto_generated_section(test_file, name)
                removed_count += 1
                print(f"  완료 (제거) → {test_file}")

    print(f"\n신규 생성: {generated_count}개 / 업데이트: {updated_count}개 / 제거: {removed_count}개")


if __name__ == "__main__":
    main()
