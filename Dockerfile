# Python 3.9 slim 이미지 기반
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지들 설치를 위해 requirements.txt 복사
COPY fastapi-app/requirements.txt .

# 종속성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 전체 복사
COPY fastapi-app/ .

RUN chmod +x start.sh

CMD ["bash", "start.sh"]
