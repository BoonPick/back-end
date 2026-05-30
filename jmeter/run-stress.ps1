<#
.SYNOPSIS
  스트레스 테스트 — 동시 사용자를 단계적으로(10→50→100→200→400) 올리며 한계점을 찾는다.
  각 단계는 같은 엔드포인트를 duration 초 동안 부하, 단계별 결과를 모아 비교표 + 한계점 출력.
.EXAMPLE
  .\run-stress.ps1 -TargetHost 163.239.77.78 -Port 8000 -Path /api/board
  .\run-stress.ps1 -Steps 10,50,100,200,400,800 -Duration 90
.NOTES
  -Path /api/keywords 로 바꾸면 가벼운 쿼리로 "커넥션 풀 한계"를 더 선명하게 본다.
#>
param(
  [string]$TargetHost = "163.239.77.78",
  [int]$Port = 3000,
  [int[]]$Steps = @(10, 50, 100, 200, 400),
  [int]$Duration = 60,
  [int]$RampUp = 10,
  [string]$Path = "/api/board",
  [double]$MaxErrorRate = 1.0,
  [double]$MaxP95 = 1000.0
)
# docker compose 는 진행상황을 stderr 로 출력하므로 Stop 을 켜면 정상 동작도 중단된다 → 끄고 진행.
$compose = Join-Path (Split-Path $PSScriptRoot -Parent) "docker-compose.yml"
$jtls = @()

foreach ($s in $Steps) {
  Write-Host "`n=== STRESS STEP: 동시 ${s}명 / ${Duration}s  ($Path) ===" -ForegroundColor Cyan
  # 이전 실행물이 남아 결과에 섞이지 않도록 단계 파일을 먼저 제거(이중 안전장치).
  $jtl = Join-Path $PSScriptRoot "results\stress-$s.jtl"
  Remove-Item $jtl -ErrorAction SilentlyContinue
  Remove-Item (Join-Path $PSScriptRoot "results\stress-$s-report") -Recurse -Force -ErrorAction SilentlyContinue
  $env:LT_PLAN     = "stress_test.jmx"
  $env:LT_HOST     = $TargetHost
  $env:LT_PORT     = "$Port"
  $env:LT_THREADS  = "$s"
  $env:LT_RAMPUP   = "$RampUp"
  $env:LT_DURATION = "$Duration"
  $env:LT_THINKTIME= "0"
  $env:LT_PATH     = $Path
  $env:LT_OUT      = "stress-$s"
  docker compose -f $compose --profile loadtest run --rm jmeter
  if (Test-Path $jtl) { $jtls += $jtl } else { Write-Host "  (경고) ${s}명 단계 결과 파일 없음 — 건너뜀" -ForegroundColor Red }
}

Write-Host "`n================ 스트레스 단계 비교 ================" -ForegroundColor Yellow
if ($jtls.Count -gt 0) {
  python (Join-Path $PSScriptRoot "ci\summarize.py") --max-error-rate $MaxErrorRate --max-p95 $MaxP95 @jtls
}
