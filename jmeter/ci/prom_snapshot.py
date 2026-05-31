#!/usr/bin/env python3
"""부하테스트 직후 Prometheus 서버측 스냅샷을 사람이 읽기 좋은 텍스트로 출력.
현재값(instant) + 테스트 구간 피크(max_over_time)를 함께 보여준다.
Prometheus 접근 불가/지표 없음에도 빌드를 깨지 않고 안내문만 남긴다(항상 exit 0).

사용:
    python3 prom_snapshot.py --prom-url http://163.239.77.78:9090 --window 15m
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request

# 한글 출력이 로케일(cp949/C)에 막히지 않도록 stdout 을 UTF-8 로 고정
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def q(prom, expr):
    url = prom.rstrip("/") + "/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.load(r)
        res = data.get("data", {}).get("result", [])
        if not res:
            return None
        return float(res[0]["value"][1])
    except Exception:
        return None


def f(v, unit="", nd=2):
    return "N/A" if v is None else f"{v:.{nd}f}{unit}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prom-url", default="http://163.239.77.78:9090")
    ap.add_argument("--window", default="15m", help="피크(max_over_time) 계산 구간")
    a = ap.parse_args()
    p, w = a.prom_url, a.window

    if q(p, "vector(1)") is None:
        print(f"[서버 스냅샷] Prometheus({p}) 접근 불가 — 서버측 지표 생략")
        return 0

    rps_now = q(p, 'sum(rate(http_requests_total{handler!="/metrics"}[1m]))')
    rps_pk = q(p, f'max_over_time((sum(rate(http_requests_total{{handler!="/metrics"}}[1m])))[{w}:15s])')
    err = q(p, '100 * (sum(rate(http_requests_total{status="5xx"}[1m])) or vector(0)) / clamp_min(sum(rate(http_requests_total{handler!="/metrics"}[1m])),1)')
    p95 = q(p, "histogram_quantile(0.95, sum(rate(http_request_duration_highr_seconds_bucket[1m])) by (le))")
    p99 = q(p, "histogram_quantile(0.99, sum(rate(http_request_duration_highr_seconds_bucket[1m])) by (le))")
    conn_now = q(p, "mysql_global_status_threads_connected")
    conn_pk = q(p, f"max_over_time(mysql_global_status_threads_connected[{w}])")
    conn_max = q(p, "mysql_global_variables_max_connections")
    running_pk = q(p, f"max_over_time(mysql_global_status_threads_running[{w}])")
    qrate_now = q(p, "rate(mysql_global_status_questions[1m])")
    qrate_pk = q(p, f"max_over_time((rate(mysql_global_status_questions[1m]))[{w}:15s])")
    slow = q(p, "rate(mysql_global_status_slow_queries[1m])")
    cpu = q(p, '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)')
    mem = q(p, "100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)")

    usage = (100 * conn_pk / conn_max) if (conn_pk is not None and conn_max) else None

    print(f"[서버 스냅샷 — 피크구간 {w}]")
    print(f"- RPS(서버):        현재 {f(rps_now,' req/s')} / 피크 {f(rps_pk,' req/s')}")
    print(f"- 5xx 에러율:        {f(err,' %')}")
    print(f"- p95 / p99 지연:    {f(p95,' s',3)} / {f(p99,' s',3)}")
    print(f"- DB 커넥션:         현재 {f(conn_now,'',0)} / 피크 {f(conn_pk,'',0)} / 한계 {f(conn_max,'',0)}  (피크 사용률 {f(usage,' %')})")
    print(f"- DB 실행중쿼리 피크: {f(running_pk,'',0)}")
    print(f"- DB 쿼리 처리율:    현재 {f(qrate_now,' /s')} / 피크 {f(qrate_pk,' /s')}")
    print(f"- 슬로우쿼리:        {f(slow,' /s')}")
    print(f"- 서버 CPU:          {f(cpu,' %')}")
    print(f"- 서버 메모리:       {f(mem,' %')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
