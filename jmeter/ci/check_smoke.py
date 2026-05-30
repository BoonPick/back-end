#!/usr/bin/env python3
"""JMeter 결과(.jtl)를 읽어 성능 임계치를 검사하는 CI 게이트.

에러율 또는 p95 응답시간이 기준을 넘으면 비정상 종료(exit 1)하여 빌드를 실패시킨다.

사용:
    python check_smoke.py results.jtl --max-error-rate 0 --max-p95 800
옵션:
    --label   특정 라벨(부분일치)만 평가 (기본: 전체 샘플)
"""
import argparse
import csv
import sys


def percentile(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jtl", help="JMeter 결과 jtl(CSV) 경로")
    ap.add_argument("--max-error-rate", type=float, default=0.0,
                    help="허용 최대 에러율(%%). 초과 시 실패")
    ap.add_argument("--max-p95", type=float, default=800.0,
                    help="허용 최대 p95 응답시간(ms). 초과 시 실패")
    ap.add_argument("--label", default=None,
                    help="평가 대상 라벨(부분일치). 기본은 전체")
    args = ap.parse_args()

    rows = []
    try:
        with open(args.jtl, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if args.label and args.label not in r.get("label", ""):
                    continue
                rows.append(r)
    except FileNotFoundError:
        print(f"[FAIL] 결과 파일 없음: {args.jtl}")
        return 2

    if not rows:
        print("[FAIL] 평가할 샘플이 없습니다 (테스트가 요청을 보내지 못함).")
        return 2

    total = len(rows)
    errors = sum(1 for r in rows if r.get("success", "").lower() != "true")
    elapsed = [float(r["elapsed"]) for r in rows if r.get("elapsed")]

    err_rate = errors / total * 100.0
    p95 = percentile(elapsed, 95)
    p99 = percentile(elapsed, 99)
    avg = sum(elapsed) / len(elapsed) if elapsed else 0.0
    mx = max(elapsed) if elapsed else 0.0

    print("=" * 52)
    print(" JMeter Smoke 결과")
    print("=" * 52)
    print(f"  총 요청      : {total}")
    print(f"  에러         : {errors}  ({err_rate:.2f}%)")
    print(f"  평균         : {avg:.0f} ms")
    print(f"  p95          : {p95:.0f} ms")
    print(f"  p99          : {p99:.0f} ms")
    print(f"  최대         : {mx:.0f} ms")
    print("-" * 52)
    print(f"  기준: 에러율 <= {args.max_error_rate:.2f}% , p95 <= {args.max_p95:.0f}ms")
    print("=" * 52)

    failed = False
    if err_rate > args.max_error_rate:
        print(f"[FAIL] 에러율 {err_rate:.2f}% > 기준 {args.max_error_rate:.2f}%")
        failed = True
    if p95 > args.max_p95:
        print(f"[FAIL] p95 {p95:.0f}ms > 기준 {args.max_p95:.0f}ms")
        failed = True

    if failed:
        print(">>> SMOKE FAILED")
        return 1
    print(">>> SMOKE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
