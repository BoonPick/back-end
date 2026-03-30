pipeline {
    agent any
    
    environment {
        // Docker Hub 정보
        DOCKER_HUB_USER = "jaeyoungkimdockerhub"
        IMAGE_NAME = "${DOCKER_HUB_USER}/boonpick-backend" // 백엔드용 이미지 이름
        DOCKER_HUB_CREDS = "docker-hub-credentials" // CICDtest와 동일한 자격증명 ID

        // 배포 서버 정보
        TARGET_SERVER = "163.239.77.78" 
        TARGET_USER = "sogang018@SGVDI.local"
        SSH_CRED_ID = "team" // CICDtest와 동일한 SSH 자격증명 ID
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build and Push to Docker Hub') {
            steps {
                script {
                    // 1. 도커 허브 로그인 및 이미지 빌드/푸시
                    docker.withRegistry('', "${DOCKER_HUB_CREDS}") {
                        def myImage = docker.build("${IMAGE_NAME}:${env.BUILD_NUMBER}")
                        myImage.push()
                        myImage.push('latest')
                    }
                }
            }
        }

        stage('Deploy to Remote Server') {
            steps {
                sshagent(["${SSH_CRED_ID}"]) {
                    // 2. 배포 서버에서 이미지 Pull 및 실행 (백엔드 포트 8000 사용)
                    sh """
                        ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "
                            docker pull ${IMAGE_NAME}:latest && \\
                            docker stop boonpick-backend-container 2>/dev/null || true && \\
                            docker rm boonpick-backend-container 2>/dev/null || true && \\
                            docker run -d --name boonpick-backend-container -p 8000:8000 ${IMAGE_NAME}:latest && \\
                            docker image prune -f
                        "
                    """
                }
            }
        }
    }
}
