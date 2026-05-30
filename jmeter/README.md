# JMeter 부하테스트

BoonPick FastAPI 백엔드의 읽기 전용(GET) 엔드포인트를 대상으로 한 부하테스트 구성.

```
jmeter/
├── fastapi_test_plan.jmx   # 테스트 플랜 (GET /api/keywords, GET /api/board)
├── Dockerfile              # JMeter 5.6.3 실행 이미지
├── run-test.sh             # 실행 전 이전 산출물 정리 래퍼
└── results/                # 실행 결과(.jtl) + HTML 리포트 (git 제외)
```

## 사전 조건

1. **Docker Desktop 실행 중**
2. **FastAPI 가 호스트에서 기동 중** (`uvicorn main:app --host 0.0.0.0 --port 8000`)
   - 컨테이너의 JMeter 는 `host.docker.internal:8000` 으로 호스트에 접근한다.

## 실행

```bash
# 백엔드 디렉터리(docker-compose.yml 위치)에서
docker compose --profile loadtest run --rm jmeter
```

기본 플랜은 `board_smoke.jmx`(게시판 동시 10명). 결과:
- `jmeter/results/result.jtl` — 원시 결과
- `jmeter/results/result-report/index.html` — HTML 대시보드 (브라우저로 열기)

> 플랜/출력은 `LT_PLAN`, `LT_OUT` 환경변수로 바꾼다. Load/Stress 는 아래 전용 드라이버 사용을 권장.

## 시나리오별 파라미터 (환경변수로 주입)

| 변수 | 기본값 | 의미 |
|------|--------|------|
| `LT_THREADS` | 10 | 동시 사용자(스레드) 수 |
| `LT_RAMPUP` | 5 | 전체 스레드가 뜨기까지(초) |
| `LT_DURATION` | 30 | 부하 유지 시간(초) |
| `LT_THINKTIME` | 200 | 요청 간 think time(ms) |
| `LT_HOST` | host.docker.internal | 대상 호스트 |
| `LT_PORT` | 8000 | 대상 포트 |

```bash
# Smoke (매 빌드용, 가볍게)
LT_THREADS=10 LT_DURATION=30 docker compose --profile loadtest run --rm jmeter

# Load (예상 트래픽)
LT_THREADS=50 LT_DURATION=300 docker compose --profile loadtest run --rm jmeter

# Stress (한계 탐색 — 단계적으로 올려가며 반복)
LT_THREADS=200 LT_RAMPUP=30 LT_DURATION=120 docker compose --profile loadtest run --rm jmeter
```

## 모니터링 연동

부하를 주는 동안 서버 측 지표는 이미 구축된 스택에서 확인:

```bash
docker compose up -d prometheus grafana node-exporter
```

- Prometheus: http://localhost:9090 (Status → Targets 에서 `fastapi` UP 확인)
- Grafana:    http://localhost:3001 (admin / admin)

JMeter 리포트(클라이언트 관점)와 Grafana(서버 관점)를 **교차 검증**한다.

## ⚠️ 주의

- 부하 대상은 **GET 엔드포인트만**. `/api/recommendations`(LLM 과금), `/api/auth/send-code`(실제 메일),
  `/api/admin/crawl`·`/notify`(외부 크롤링/대량 메일)는 절대 부하 대상에 넣지 말 것.
- `run-test.sh` 가 매 실행 시 `results/` 의 이전 `report/`·`result.jtl` 을 삭제한다.

---

## Load / Stress 테스트 (팀 서버 대상)

배포된 팀 서버를 컨테이너 JMeter 로 외부에서 부하한다. PowerShell 드라이버가 실행 + 결과 요약까지.

```
jmeter/
├── load_test.jmx      # 부하: board 70% / 상세 20% / keywords 10% 혼합
├── stress_test.jmx    # 스트레스: 단일 엔드포인트, 동시 사용자 주입형
├── ids.csv            # 상세 조회용 게시글 id 목록
├── gen-ids.ps1        # 라이브 서버에서 ids.csv 갱신
├── run-load.ps1       # 부하 1회 실행 + 요약
├── run-stress.ps1     # 단계 상승(10→…→400) + 한계점 표
└── ci/summarize.py    # jtl 분석(라벨별/단계별, 한계점 탐지)
```

### 0) 사전: 상세 조회용 id 갱신 (Load 전 1회)

```powershell
cd back-end\jmeter
.\gen-ids.ps1 -BaseUrl http://<팀서버:포트> -Size 100   # ids.csv 갱신
```
> ⚠️ `<팀서버:포트>` 는 **백엔드 API 공개 주소**. 모르면 board 상세가 전부 404 가 되어 결과가 왜곡된다.

### 1) Load — 동시 100명 혼합 트래픽

```powershell
.\run-load.ps1 -TargetHost <IP> -Port <PORT> -Threads 100 -Duration 300
```
- 출력: `results/load-report/index.html` + 콘솔에 라벨별 p95/TPS/에러율
- 판단: p95·에러율이 SLA(예: p95<1s, err<1%) 안에 드는지

### 2) Stress — 단계 상승으로 한계점 탐색

```powershell
# 게시판(실사용 관점) 한계
.\run-stress.ps1 -TargetHost <IP> -Port <PORT> -Steps 10,50,100,200,400 -Duration 60

# 커넥션 풀 한계를 더 선명하게 (가벼운 쿼리)
.\run-stress.ps1 -TargetHost <IP> -Port <PORT> -Path /api/keywords -Steps 10,50,100,200,400
```
- 각 단계 독립 측정 → 비교표 출력:
  ```
    users  samples  err%   avg   p95   p99   tps
       10    1800   0.00    35    80   120   29.8
       50    8500   0.00    42   110   180  141.0
      100   15000   0.10    95   320   600  248.0
      200   12000   8.40   850  4900  5000  180.0  <== 한계 초과
  ```
- **"언제/어디서 터지는지"**: 첫 `한계 초과` 단계 = 서버가 버티는 동시 사용자 상한.
  같은 시점 Grafana 에서 `threads_connected` / CPU 를 보면 **무엇이** 병목인지(커넥션·CPU·DB) 확인.

### Jenkins 에서 버튼으로 실행 (on-demand) ★

로컬 PC 대신 **Jenkins 에이전트가 부하를 생성**하고 결과를 빌드 페이지에 게시한다.
파이프라인 정의: 레포 루트 `Jenkinsfile.loadtest`.

**최초 1회 잡 생성:**
1. Jenkins → New Item → **Pipeline** 선택
2. Pipeline → Definition: **Pipeline script from SCM**
   - SCM: Git, 이 백엔드 레포 / Branch: `*/main`
   - **Script Path: `Jenkinsfile.loadtest`**
3. 저장

**실행:** 잡 페이지 → **`Build with Parameters`** 버튼
- `TEST_TYPE`: smoke / load / **stress** 선택
- `THREADS`, `DURATION`, `STRESS_STEPS`(예: `10,50,100,200,400`), `ENDPOINT_PATH` 입력
- Build 클릭 → 콘솔에 요약/한계점 표, 좌측 **JMeter Report** 에 HTML, Artifacts 에 jtl

**필요 플러그인:** HTML Publisher(리포트 열람용). 없으면 리포트는 Artifacts 로만 받음(빌드는 정상).
**에이전트 요구:** `curl`, `tar`, `python3` (메인 `Jenkinsfile` 과 동일 환경이면 충족).

> 이렇게 하면 PC 를 꺼도, 팀 누구나 Jenkins 에서 버튼만 눌러 부하테스트를 돌리고 결과를 공유할 수 있다.

### 부하 중 서버 관찰 (필수)

부하를 거는 동안 **로컬에서 모니터링 스택**을 띄워 팀 서버를 스크레이프하거나, 팀 서버에 이미 떠 있는
Grafana 를 본다. JMeter(클라이언트 관점) + Grafana(서버 관점)를 **교차 검증**해야 병목이 보인다.

> ⚠️ **운영 주의**: 실서비스/공용 서버에 stress 를 걸기 전 팀원과 시간대를 합의할 것. 400명 단계는
> 서버를 의도적으로 무너뜨릴 수 있다. 처음엔 낮은 단계부터, 짧은 duration 으로.

---

## CI 성능 스모크 게이트 (매 빌드)

`board_smoke.jmx` + `.github/workflows/perf-smoke.yml` 로 **push/PR 마다** 게시판을 동시 10명이
두드려 성능 회귀를 잡는다. 부하가 아니라 *경보기*.

```
jmeter/
├── board_smoke.jmx      # 게시판 전용 스모크 (GET /api/board, 동시 10명)
└── ci/
    ├── schema.sql       # CI 전용 최소 스키마 (board 쿼리에 필요한 테이블)
    ├── seed.sql         # CI 시드 데이터 30건
    └── check_smoke.py   # result.jtl 파싱 → 에러율/p95 기준 초과 시 빌드 실패
```

흐름: MySQL 서비스 기동 → 스키마/시드 적재 → uvicorn 기동 → JMeter 10명/20초 →
`check_smoke.py` 로 **에러율 0% / p95 ≤ 800ms** 검사 → 위반 시 빌드 FAIL + 리포트 아티팩트 업로드.

기준 조정은 워크플로우의 `MAX_ERROR_RATE` / `MAX_P95_MS` 환경변수로.

### 로컬에서 게이트 로직만 검증

```bash
python jmeter/ci/check_smoke.py jmeter/results/result.jtl --label board --max-error-rate 0 --max-p95 800
```

### Jenkins 에 넣고 싶다면 (메인 CI/CD 가 Jenkins 인 경우)

`Jenkinsfile` 의 `Test & Coverage` 와 `Build` 사이에 스테이지 추가:

```groovy
stage('Perf Smoke') {
    steps {
        sh '''
            . venv/bin/activate
            cd fastapi-app && nohup uvicorn main:app --host 0.0.0.0 --port 8000 >/tmp/uvicorn.log 2>&1 &
            cd ..
            for i in $(seq 1 30); do curl -sf "http://localhost:8000/api/board?page=1&size=1" && break || sleep 2; done
            JM=/opt/apache-jmeter-5.6.3
            $JM/bin/jmeter -n -t jmeter/board_smoke.jmx -Jhost=localhost -Jport=8000 \
              -Jthreads=10 -Jrampup=2 -Jduration=20 -l results.jtl -e -o report
            python3 jmeter/ci/check_smoke.py results.jtl --label board --max-error-rate 0 --max-p95 800
        '''
    }
}
```
(Jenkins 에이전트에 JMeter 설치 + DB 접속 환경 전제. GitHub Actions 쪽이 self-contained 라 권장.)

---

## mysqld-exporter (DB 커넥션 병목 시각화)

부하 중 **커넥션 풀 고갈**을 Grafana 로 보기 위해 `prom/mysqld-exporter` 를 compose 에 추가했다.

1. `.env.example` → `.env` 복사 후 접속정보 입력
2. MySQL 에 모니터링 계정 생성:
   ```sql
   CREATE USER 'exporter'@'%' IDENTIFIED BY 'change-me' WITH MAX_USER_CONNECTIONS 3;
   GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'exporter'@'%';
   FLUSH PRIVILEGES;
   ```
3. 기동: `docker compose up -d mysqld-exporter prometheus grafana`
4. Prometheus Targets 에서 `mysql` UP 확인 → Grafana 에서 아래 지표 관찰
   - `mysql_global_status_threads_connected` — 현재 커넥션 수
   - `mysql_global_status_max_used_connections` — 피크 커넥션
   - `mysql_global_variables_max_connections` — 한계치

부하를 올릴수록 `threads_connected` 가 `max_connections` 에 붙는 게 보이면 → 커넥션 풀 도입 근거.
