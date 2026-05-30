<#
.SYNOPSIS
  부하(Load) 테스트 — 게시판 혼합 트래픽(board 70% / 상세 20% / keywords 10%), 동시 100명.
  팀 서버(배포본)를 대상으로 컨테이너 JMeter 가 외부 타깃을 때린다.
.EXAMPLE
  .\run-load.ps1 -TargetHost 163.239.77.78 -Port 8000 -Threads 100 -Duration 300
.NOTES
  실행 전 .\gen-ids.ps1 로 ids.csv 를 실제 서버 기준으로 갱신할 것(상세 조회 404 방지).
#>
param(
  [string]$TargetHost = "163.239.77.78",
  [int]$Port = 3000,
  [int]$Threads = 100,
  [int]$RampUp = 30,
  [int]$Duration = 300,
  [int]$ThinkTime = 300
)
# docker compose 는 진행상황을 stderr 로 출력하므로 Stop 을 켜면 정상 동작도 중단된다 → 끄고 진행.
$compose = Join-Path (Split-Path $PSScriptRoot -Parent) "docker-compose.loadtest.yml"

$env:LT_PLAN     = "load_test.jmx"
$env:LT_HOST     = $TargetHost
$env:LT_PORT     = "$Port"
$env:LT_THREADS  = "$Threads"
$env:LT_RAMPUP   = "$RampUp"
$env:LT_DURATION = "$Duration"
$env:LT_THINKTIME= "$ThinkTime"
$env:LT_OUT      = "load"

Write-Host "=== Load: $TargetHost`:$Port  동시 ${Threads}명 / ${Duration}s ===" -ForegroundColor Cyan
docker compose -f $compose run --rm jmeter

$jtl = Join-Path $PSScriptRoot "results\load.jtl"
if (Test-Path $jtl) {
  python (Join-Path $PSScriptRoot "ci\summarize.py") $jtl
  Write-Host "`nHTML 리포트: $(Join-Path $PSScriptRoot 'results\load-report\index.html')" -ForegroundColor Green
}
