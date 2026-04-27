pipeline {
    agent any

    parameters {
        string(
            name: 'BRANCH',
            defaultValue: '',
            description: '수동 실행 시 브랜치 지정. 비워두면 push된 브랜치 자동 감지.'
        )
    }

    environment {
        DOCKER_HUB_USER  = "jaeyoungkimdockerhub"
        IMAGE_NAME       = "${DOCKER_HUB_USER}/boonpick-backend"
        DOCKER_HUB_CREDS = "docker-hub-credentials"

        TARGET_SERVER = "163.239.77.78"
        TARGET_USER   = "sogang018@SGVDI.local"
        SSH_CRED_ID   = "team"

        DB_HOST     = credentials('BOONPICK_DB_HOST')
        DB_USER     = credentials('BOONPICK_DB_USER')
        DB_PASSWORD = credentials('BOONPICK_DB_PASSWORD')
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    // 파라미터가 있으면 사용, 없으면 webhook이 감지한 브랜치, 그것도 없으면 main
                    def branch = params.BRANCH?.trim()
                    if (!branch) {
                        branch = env.GIT_BRANCH?.replaceAll('origin/', '')?.trim() ?: 'main'
                    }
                    env.DEPLOY_BRANCH = branch
                    env.IMAGE_TAG = "${branch.replaceAll('/', '-')}-${env.BUILD_NUMBER}"
                }

                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "*/${env.DEPLOY_BRANCH}"]],
                    userRemoteConfigs: scm.userRemoteConfigs
                ])
                echo "배포 브랜치: ${env.DEPLOY_BRANCH}"
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

        stage('Cleanup Stale Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    cd fastapi-app
                    python scripts/cleanup_stale_tests.py
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
                      --cov-report=term \
                    || [ $? -eq 5 ]
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
                        def myImage = docker.build("${IMAGE_NAME}:${env.IMAGE_TAG}")
                        myImage.push()

                        // main 브랜치만 latest 태그 갱신
                        if (env.DEPLOY_BRANCH == 'main') {
                            myImage.push('latest')
                        }
                    }
                }
            }
        }

        stage('Deploy to Remote Server') {
            steps {
                script {
                    def safeBranch    = env.DEPLOY_BRANCH.replaceAll('/', '-')
                    def containerName = env.DEPLOY_BRANCH == 'main'
                        ? 'boonpick-backend-container'
                        : "boonpick-backend-${safeBranch}-container"
                    def hostPort = env.DEPLOY_BRANCH == 'main' ? '8000' : '8001'

                    echo "컨테이너: ${containerName}  포트: ${hostPort}"

                    sshagent(["${SSH_CRED_ID}"]) {
                        sh """
                            ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "
                                docker pull ${IMAGE_NAME}:${env.IMAGE_TAG} && \\
                                docker stop ${containerName} 2>/dev/null || true && \\
                                docker rm   ${containerName} 2>/dev/null || true && \\
                                docker run -d --name ${containerName} -p ${hostPort}:8000 \\
                                    -e DB_HOST=${env.DB_HOST} \\
                                    -e DB_USER=${env.DB_USER} \\
                                    -e DB_PASSWORD='${env.DB_PASSWORD}' \\
                                    ${IMAGE_NAME}:${env.IMAGE_TAG} && \\
                                docker image prune -f
                            "
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            emailext (
                subject: "✅ [Jenkins] 빌드 성공: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: """<p>빌드가 성공적으로 완료되었습니다.</p>
                         <p><b>Job:</b> ${env.JOB_NAME}<br>
                         <b>Build Number:</b> ${env.BUILD_NUMBER}<br>
                         <b>URL:</b> <a href="${env.BUILD_URL}">${env.BUILD_URL}</a></p>""",
                to: 'kjyyoung0305@gmail.com, yooncy0511@gmail.com, lee.moonjeong@gmail.com, wq0212@naver.com',
                mimeType: 'text/html'
            )
        }
        failure {
            emailext (
                subject: "❌ [Jenkins] 빌드 실패: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: """<p>빌드 중 에러가 발생했습니다. 로그를 확인해 주세요.</p>
                         <p><b>Job:</b> ${env.JOB_NAME}<br>
                         <b>Build Number:</b> ${env.BUILD_NUMBER}<br>
                         <b>Console Log:</b> <a href="${env.BUILD_URL}console">${env.BUILD_URL}console</a></p>""",
                to: 'kjyyoung0305@gmail.com, yooncy0511@gmail.com, lee.moonjeong@gmail.com, wq0212@naver.com',
                mimeType: 'text/html'
            )
        }
        always {
            echo "Pipeline 완료 — 브랜치: ${env.DEPLOY_BRANCH}"
        }
    }
}
