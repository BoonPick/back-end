<#
.SYNOPSIS
  팀 서버의 게시판에서 실제 게시글 id 목록을 받아 ids.csv 를 갱신한다.
  Load 테스트의 board 상세(GET /api/board/{id}) 가 유효한 id 를 쓰도록 하기 위함.
.EXAMPLE
  .\gen-ids.ps1 -BaseUrl http://163.239.77.78:8000 -Size 100
#>
param(
  [string]$BaseUrl = "http://163.239.77.78:3000",
  [int]$Size = 100
)
$ErrorActionPreference = "Stop"
$items = Invoke-RestMethod "$BaseUrl/api/board?page=1&size=$Size"
$ids = $items | ForEach-Object { $_.id }
if (-not $ids) { throw "게시글을 받지 못했습니다. BaseUrl/포트를 확인하세요: $BaseUrl" }
$out = Join-Path $PSScriptRoot "ids.csv"
$ids | Set-Content -Path $out -Encoding ascii
Write-Host "$($ids.Count) ids -> $out"
