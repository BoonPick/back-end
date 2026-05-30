# Apache JMeter 실행용 이미지. 비-GUI(-n) 모드로 테스트 플랜을 돌리고 HTML 리포트를 생성한다.
FROM eclipse-temurin:17-jre-jammy

ARG JMETER_VERSION=5.6.3
ENV JMETER_HOME=/opt/apache-jmeter-${JMETER_VERSION}
ENV PATH="${JMETER_HOME}/bin:${PATH}"

# 다운로드에 필요한 최소 패키지만 설치
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# JMeter 바이너리 설치 (Apache 아카이브에서 고정 버전 다운로드)
RUN curl -fSL "https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-${JMETER_VERSION}.tgz" -o /tmp/jmeter.tgz \
 && tar -xzf /tmp/jmeter.tgz -C /opt \
 && rm /tmp/jmeter.tgz

WORKDIR /test

# 테스트 플랜을 이미지에 포함(self-contained). compose 에서 같은 경로로 마운트하면
# 재빌드 없이 플랜 수정 내용을 바로 반영할 수 있다.
COPY fastapi_test_plan.jmx /test/fastapi_test_plan.jmx
COPY run-test.sh /run-test.sh
RUN chmod +x /run-test.sh

# 결과/리포트 디렉터리를 매 실행마다 정리한 뒤 jmeter 를 실행하는 래퍼
ENTRYPOINT ["/run-test.sh"]
