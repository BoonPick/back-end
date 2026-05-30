#!/bin/sh
# JMeter 실행 래퍼.
# JMeter 의 -l(결과 jtl)/-j(로그)/-e -o(HTML 리포트)는 기존 파일이나 비어있지 않은
# 폴더가 있으면 실패하므로, 인자에서 해당 출력 경로를 찾아 매 실행 전에 정리한다.
set -e

prev=""
for a in "$@"; do
  case "$prev" in
    -o) rm -rf "$a" ;;
    -l) rm -f "$a" ;;
    -j) rm -f "$a" ;;
  esac
  prev="$a"
done

exec jmeter "$@"
