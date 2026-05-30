#!/usr/bin/env python3
"""JMeter 결과(.jtl) 1개 이상을 요약/비교한다.

- 단일 파일: 라벨별 + 전체 지표 표
- 다중 파일(스트레스 단계별): 파일명에서 동시 사용자 수(숫자)를 추출해 단계 비교표 + 한계점 탐지

사용:
    python summarize.py results/load.jtl
    python summarize.py --max-error-rate 1 --max-p95 1000 results/stress-10.jtl results/stress-50.jtl ...
"""
import argparse
import csv
import re
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


def load(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def metrics(rows):
    n = len(rows)
    if n == 0:
        return None
    errors = sum(1 for r in rows if r.get("success", "").lower() != "true")
    elapsed = [float(r["elapsed"]) for r in rows if r.get("elapsed")]
    ts = [int(r["timeStamp"]) for r in rows if r.get("timeStamp")]
    span = (max(ts) - min(ts)) / 1000.0 if len(ts) > 1 else 1.0
    span = span if span > 0 else 1.0
    return {
        "samples": n,
        "errors": errors,
        "err_rate": errors / n * 100.0,
        "avg": sum(elapsed) / len(elapsed) if elapsed else 0.0,
        "p95": percentile(elapsed, 95),
        "p99": percentile(elapsed, 99),
        "max": max(elapsed) if elapsed else 0.0,
        "tps": n / span,
    }


def step_of(path):
    m = re.search(r"(\d+)", path.replace("\\", "/").split("/")[-1])
    return int(m.group(1)) if m else None


def per_label(rows):
    labels = {}
    for r in rows:
        labels.setdefault(r.get("label", "?"), []).append(r)
    return labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jtl", nargs="+", help="JMeter 결과 jtl 경로(들)")
    ap.add_argument("--max-error-rate", type=float, default=1.0,
                    help="한계점 판정 에러율 임계(%%)")
    ap.add_argument("--max-p95", type=float, default=1000.0,
                    help="한계점 판정 p95 임계(ms)")
    args = ap.parse_args()

    if len(args.jtl) == 1:
        rows = load(args.jtl[0])
        if not rows:
            print("샘플 없음"); return 2
        print(f"\n파일: {args.jtl[0]}")
        print(f"{'label':<24}{'count':>8}{'err%':>8}{'avg':>8}{'p95':>8}{'p99':>8}{'tps':>9}")
        print("-" * 73)
        for label, lr in per_label(rows).items():
            m = metrics(lr)
            print(f"{label:<24}{m['samples']:>8}{m['err_rate']:>8.2f}{m['avg']:>8.0f}"
                  f"{m['p95']:>8.0f}{m['p99']:>8.0f}{m['tps']:>9.1f}")
        t = metrics(rows)
        print("-" * 73)
        print(f"{'TOTAL':<24}{t['samples']:>8}{t['err_rate']:>8.2f}{t['avg']:>8.0f}"
              f"{t['p95']:>8.0f}{t['p99']:>8.0f}{t['tps']:>9.1f}")
        return 0

    # 다중 파일 = 스트레스 단계 비교
    steps = []
    for p in args.jtl:
        rows = load(p)
        m = metrics(rows)
        if m is None:
            print(f"[skip] 샘플 없음: {p}"); continue
        m["step"] = step_of(p)
        m["file"] = p
        steps.append(m)
    steps.sort(key=lambda x: (x["step"] is None, x["step"]))

    print(f"\n{'users':>7}{'samples':>9}{'err%':>8}{'avg':>8}{'p95':>8}{'p99':>8}{'max':>9}{'tps':>9}")
    print("-" * 66)
    breaking = None
    for m in steps:
        flag = ""
        if m["err_rate"] > args.max_error_rate or m["p95"] > args.max_p95:
            flag = "  <== 한계 초과"
            if breaking is None:
                breaking = m
        u = m["step"] if m["step"] is not None else "?"
        print(f"{str(u):>7}{m['samples']:>9}{m['err_rate']:>8.2f}{m['avg']:>8.0f}"
              f"{m['p95']:>8.0f}{m['p99']:>8.0f}{m['max']:>9.0f}{m['tps']:>9.1f}{flag}")
    print("-" * 66)
    print(f"기준: 에러율 <= {args.max_error_rate:.1f}% , p95 <= {args.max_p95:.0f}ms")
    if breaking:
        print(f">>> 한계점(첫 초과 단계): 동시 {breaking['step']}명 "
              f"(err {breaking['err_rate']:.2f}%, p95 {breaking['p95']:.0f}ms)")
    else:
        print(">>> 측정 범위 내에서는 한계 미도달 — 더 높은 단계로 확장 권장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
