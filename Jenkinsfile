pipeline {
    agent any

    environment {
        // Docker Hub 정보
        DOCKER_HUB_USER = "jaeyoungkimdockerhub"
        IMAGE_NAME = "${DOCKER_HUB_USER}/boonpick-backend"
        DOCKER_HUB_CREDS = "docker-hub-credentials"

        // 배포 서버 정보
        TARGET_SERVER = "163.239.77.78"
        TARGET_USER = "sogang018@SGVDI.local"
        SSH_CRED_ID = "team"

        // DB 접속 정보
        DB_HOST = credentials('BOONPICK_DB_HOST')
        DB_USER = credentials('BOONPICK_DB_USER')
        DB_PASSWORD = credentials('BOONPICK_DB_PASSWORD')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup Environment & Install Dependencies') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r fastapi-app/requirements.txt
                '''
            }
        }

        stage('Test & Coverage') {
            steps {
                sh '''
                    . venv/bin/activate
                    mkdir -p pytest_report
                    cd fastapi-app
                    pytest tests \
                      --html=../pytest_report/report.html \
                      --self-contained-html \
                      --cov=. \
                      --cov-report=html:../htmlcov \
                      --cov-report=term
                '''
            }
            post {
                always {
                    publishHTML(target: [
                        reportName : 'Pytest HTML Report',
                        reportDir  : 'pytest_report',
                        reportFiles: 'report.html',
                        keepAll    : true,
                        alwaysLinkToLastBuild: true,
                        allowMissing: true
                    ])
                    publishHTML(target: [
                        reportName : 'Coverage Report',
                        reportDir  : 'htmlcov',
                        reportFiles: 'index.html',
                        keepAll    : true,
                        alwaysLinkToLastBuild: true,
                        allowMissing: true
                    ])
                }
            }
        }

        stage('Build and Push to Docker Hub') {
            steps {
                script {
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
                    sh """
                        ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "
                            docker pull ${IMAGE_NAME}:latest && \\
                            docker stop boonpick-backend-container 2>/dev/null || true && \\
                            docker rm boonpick-backend-container 2>/dev/null || true && \\
                            docker run -d --name boonpick-backend-container -p 8000:8000 \\
                            -e DB_HOST=${env.DB_HOST} \\
                            -e DB_USER=${env.DB_USER} \\
                            -e DB_PASSWORD='${env.DB_PASSWORD}' \\
                            ${IMAGE_NAME}:latest && \\
                            docker image prune -f
                        "
                    """
                }
            }
        }
    }

    post {
        always {
            echo 'Pipeline completed.'
        }
    }
}
