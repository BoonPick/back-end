pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Build & Deploy') {
            steps {
                // 1. 도커 이미지 빌드
                sh 'docker build -t boonpick-backend .'
                
                // 2. 기존 컨테이너 중지 및 삭제 (이미 존재할 경우 대비)
                sh 'docker stop boonpick-backend-container || true'
                sh 'docker rm boonpick-backend-container || true'
                
                // 3. 새 컨테이너 실행 (8000 포트 연결)
                sh 'docker run -d --name boonpick-backend-container -p 8000:8000 boonpick-backend'
            }
        }
    }
}
