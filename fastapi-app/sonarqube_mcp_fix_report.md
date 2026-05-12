# SonarQube MCP Fix Report — Boon-Claude

## 작업 브랜치

`sonar-mcp`

---

## 1. 이슈 조회 개요

SonarQube MCP를 통해 Boon-Claude 프로젝트의 BLOCKER/CRITICAL 이슈 13건을 조회하였으며,
기존 기능 변경 위험 없이 수정 가능한 이슈를 선별하였습니다.

| 규칙 | 심각도 | 건수 | 파일 |
|------|--------|------|------|
| `python:S8410` | BLOCKER | 6 | `main.py` |
| `python:S3776` | CRITICAL | 6 | `main.py`, `crawling_noti.py`, `crawling_job.py`, `notifier.py`, `pdfviewer.py`, `scripts/cleanup_stale_tests.py` |
| `python:S5754` | CRITICAL | 1 | `scheduler.py` |

---

## 2. 선택한 이슈 및 수정 여부

### ✅ 수정 완료 — `python:S8410` BLOCKER (6건)

| 이슈 ID | 파일 | 라인 |
|---------|------|------|
| `2e9c8081` | `main.py` | 623 |
| `84c7aef1` | `main.py` | 607 |
| `be9bb423` | `main.py` | 601 |
| `588551c5` | `main.py` | 567 |
| `1a8c80d9` | `main.py` | 450 |
| `1d12a97f` | `main.py` | 451 |

**심각도:** BLOCKER — `MAINTAINABILITY: BLOCKER`

**이슈 위치:** `main.py` 내 FastAPI 엔드포인트 함수 파라미터 선언부

**원인:**
FastAPI 공식 권장 방식인 `Annotated` 타입 힌트 없이 구식 `= Query(...)` 기본값 패턴 사용.

**방치 시 위험성:**
- FastAPI 최신 버전에서 타입 검사기(mypy, pyright)와의 호환성 저하
- 의존성 주입 메타데이터가 타입 레벨에서 불투명해져 IDE 지원 손실
- SonarQube Quality Gate 통과 불가 (BLOCKER 등급)

---

### ❌ 수정 보류 — `python:S5754` CRITICAL (`scheduler.py:86`)

**보류 사유:**
기존 테스트(`test_keyboard_interrupt_is_handled_gracefully`, `test_system_exit_is_handled_gracefully`)가
이 except 블록이 **의도적으로 예외를 re-raise하지 않아야 함**을 명시적으로 검증하고 있습니다.
`raise` 추가 시 pytest exit code 2 (세션 중단) 발생 확인.

이 패턴은 스케줄러 진입점의 종료 처리 로직으로, `KeyboardInterrupt`/`SystemExit` 수신 시 "스케줄러 종료"를 로깅하고
자연 종료(exit 0)하는 **의도된 설계**입니다.

---

### ❌ 수정 보류 — `python:S3776` CRITICAL (6건, 인지 복잡도 초과)

**보류 사유:**
Cognitive Complexity 리팩토링은 핵심 비즈니스 로직(`crawling_noti.py`, `crawling_job.py` 등)의
대규모 분리를 요구하여 기능 회귀 위험이 높습니다. 이번 작업 범위 밖으로 판단합니다.

---

## 3. 수정 상세

### 수정 파일

- `fastapi-app/main.py`

### 수정 내용 요약

`from typing import List, Optional`에 `Annotated`를 추가하고,
6개의 Query 파라미터를 구식 패턴에서 권장 패턴으로 전환하였습니다.

---

### 수정 전후 코드 (Diff)

```diff
-from typing import List, Optional
+from typing import Annotated, List, Optional

 @app.get("/api/board", response_model=List[BoardItem])
 def get_board_items(
     ...
-    page: int = Query(1, ge=1),
-    size: int = Query(20, ge=1, le=100),
+    page: Annotated[int, Query(ge=1)] = 1,
+    size: Annotated[int, Query(ge=1, le=100)] = 20,
 ):

 @app.get("/api/recommendations/{item_id}", response_model=Recommendation)
-def get_recommendation(item_id: int, keywords: str = Query("")):
+def get_recommendation(item_id: int, keywords: Annotated[str, Query()] = ""):

 @app.post("/api/admin/crawl")
-def trigger_crawl(page_count: int = Query(5, ge=1, le=20)):
+def trigger_crawl(page_count: Annotated[int, Query(ge=1, le=20)] = 5):

 @app.post("/api/admin/crawl/jobs")
-def trigger_job_crawl(page_count: int = Query(3, ge=1, le=20)):
+def trigger_job_crawl(page_count: Annotated[int, Query(ge=1, le=20)] = 3):

 @app.post("/api/admin/dedup/jobs", response_model=DedupJobsResponse)
 def dedup_jobs_by_title_worktype(
-    dry_run: bool = Query(True, description="True면 영향 범위만 반환, False면 실제 삭제"),
+    dry_run: Annotated[bool, Query(description="True면 영향 범위만 반환, False면 실제 삭제")] = True,
 ):
```

### 수정 전 코드 문제

```python
# 구식 패턴 — Query()가 기본값과 메타데이터를 동시에 담아
# 타입 힌트 레벨에서 FastAPI의 의도가 불투명함
page: int = Query(1, ge=1)
```

### 수정 후 해결 방식

```python
# 권장 패턴 — Annotated로 FastAPI 메타데이터를 타입에 명시,
# 기본값은 파이썬 표준 방식으로 별도 분리
page: Annotated[int, Query(ge=1)] = 1
```

API 동작(기본값, 유효성 검사, 엔드포인트 주소)은 **완전히 동일**합니다.

---

## 4. 테스트 결과

| 테스트 파일 | 실행 결과 |
|-------------|-----------|
| `tests/test_main.py` | **107 passed** |
| `tests/test_scheduler.py` | **28 passed** |
| **합계** | **135 passed, 0 failed** |

```
======================== 135 passed, 1 warning in 1.28s ========================
```

---

## 5. SonarQube 재분석 결과

수정 후 SonarQube 재스캔이 완료되면 아래 6건이 `RESOLVED`로 전환될 예정:

| 이슈 ID | 규칙 | 라인 | 예상 상태 |
|---------|------|------|----------|
| `2e9c8081` | `python:S8410` | 623 | RESOLVED |
| `84c7aef1` | `python:S8410` | 607 | RESOLVED |
| `be9bb423` | `python:S8410` | 601 | RESOLVED |
| `588551c5` | `python:S8410` | 567 | RESOLVED |
| `1a8c80d9` | `python:S8410` | 450 | RESOLVED |
| `1d12a97f` | `python:S8410` | 451 | RESOLVED |

---

## 6. 커밋 정보

**브랜치:** `sonar-mcp`

**커밋 해시:** `d9e5c85`

**커밋 메시지:**
```
fix(sonar): resolve BLOCKER S8410 — migrate FastAPI params to Annotated type hints
```

---

## 7. 미수정 이슈 후속 권장 사항

| 이슈 | 권장 조치 |
|------|-----------|
| `crawling_noti.py:113` — Complexity 53 | 함수 분리 리팩토링 (별도 브랜치) |
| `crawling_job.py:108` — Complexity 23 | 함수 분리 리팩토링 |
| `main.py:444` — Complexity 21 | 함수 분리 리팩토링 |
| `notifier.py:140` — Complexity 17 | 함수 분리 리팩토링 |
| `pdfviewer.py:83` — Complexity 30 | 함수 분리 리팩토링 |
| `scheduler.py:86` — S5754 | 기존 테스트 설계와 충돌, 무시(Acknowledge) 처리 권장 |
