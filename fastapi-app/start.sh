#!/bin/bash
playwright install --with-deps chromium &

# 멀티워커에서 prometheus 메트릭이 워커별로 분리돼 RPS/p95 가 튀는 문제 해결:
# 멀티프로세스 모드 활성화 — 각 워커가 이 디렉터리에 메트릭을 기록하고 /metrics 가 합산 노출.
# (시작 시 이전 워커들의 잔여 파일을 비워 깨끗한 상태로 시작)
export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS:-4}
