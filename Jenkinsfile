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

        DB_HOST       = credentials('BOONPICK_DB_HOST')
        DB_USER       = credentials('BOONPICK_DB_USER')
        DB_PASSWORD   = credentials('BOONPICK_DB_PASSWORD')
        SAINT_ID      = credentials('BOONPICK_SAINT_ID')
        SAINT_PW      = credentials('BOONPICK_SAINT_PW')
        SMTP_USER     = credentials('BOONPICK_SMTP_USER')
        SMTP_PASSWORD = credentials('BOONPICK_SMTP_PASSWORD')
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
                script {
                    try {
                        sh '''
                            python3 -m venv venv
                            . venv/bin/activate
                            pip install --upgrade pip
                            pip install -r fastapi-app/requirements.txt
                        '''
                    } catch (Exception e) {
                        echo "STAGE_ERROR: ${e.getMessage()}"
                        throw e
                    }
                }
            }
        }

        stage('Cleanup Stale Tests') {
            steps {
                script {
                    try {
                        sh '''
                            . venv/bin/activate
                            cd fastapi-app
                            python scripts/cleanup_stale_tests.py
                        '''
                    } catch (Exception e) {
                        echo "STAGE_ERROR: ${e.getMessage()}"
                        throw e
                    }
                }
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
                      --cov-report=json:../coverage.json \
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
                    archiveArtifacts artifacts: 'coverage.json', fingerprint: true, allowEmptyArchive: true
                }
            }
        }

        stage('Build and Push to Docker Hub') {
            steps {
                script {
                    try {
                        docker.withRegistry('', "${DOCKER_HUB_CREDS}") {
                            def myImage = docker.build("${IMAGE_NAME}:${env.IMAGE_TAG}")
                            myImage.push()

                            // main 브랜치만 latest 태그 갱신
                            if (env.DEPLOY_BRANCH == 'main') {
                                myImage.push('latest')
                            }
                        }
                    } catch (Exception e) {
                        echo "STAGE_ERROR: ${e.getMessage()}"
                        throw e
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

                    try {
                        sshagent(["${SSH_CRED_ID}"]) {
                            sh """
                                ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "
                                    docker pull ${IMAGE_NAME}:${env.IMAGE_TAG} && \\
                                    docker stop ${containerName} 2>/dev/null || true && \\
                                    docker rm   ${containerName} 2>/dev/null || true && \\
                                    docker run -d --name ${containerName} -p ${hostPort}:8000 \\
                                        -e DB_HOST='${env.DB_HOST}' \\
                                        -e DB_USER='${env.DB_USER}' \\
                                        -e DB_PASSWORD='${env.DB_PASSWORD}' \\
                                        -e SAINT_ID='${env.SAINT_ID}' \\
                                        -e SAINT_PW='${env.SAINT_PW}' \\
                                        -e SMTP_HOST=smtp.gmail.com \\
                                        -e SMTP_PORT=587 \\
                                        -e SMTP_USER='${env.SMTP_USER}' \\
                                        -e SMTP_PASSWORD='${env.SMTP_PASSWORD}' \\
                                        -e MAIL_FROM_NAME=BoonPick \\
                                        -e MAIL_FROM_EMAIL='${env.SMTP_USER}' \\
                                        ${IMAGE_NAME}:${env.IMAGE_TAG} && \\
                                    docker image prune -f
                                "
                            """
                        }
                    } catch (Exception e) {
                        echo "STAGE_ERROR: ${e.getMessage()}"
                        throw e
                    }
                }
            }
        }

        stage('Deploy Monitoring Stack') {
            // main 배포일 때만 동작. 모니터링 컨테이너는 앱과 라이프사이클이 분리돼 있어
            // 매 배포마다 재기동되지 않고, 설정 파일이 바뀌었을 때만 반영됨.
            when {
                expression { env.DEPLOY_BRANCH == 'main' }
            }
            steps {
                script {
                    def remoteDir = "~/boonpick-monitoring"
                    try {
                        sshagent(["${SSH_CRED_ID}"]) {
                            sh """
                                # 1) 설정 디렉터리 준비 후 compose / prometheus 설정 전송
                                ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} \\
                                    "mkdir -p ${remoteDir}/prometheus"
                                scp -o StrictHostKeyChecking=no docker-compose.yml \\
                                    ${TARGET_USER}@${TARGET_SERVER}:${remoteDir}/docker-compose.yml
                                scp -o StrictHostKeyChecking=no prometheus/prometheus.yml \\
                                    ${TARGET_USER}@${TARGET_SERVER}:${remoteDir}/prometheus/prometheus.yml

                                # 2) 컨테이너 기동(또는 설정 갱신). prometheus는 재시작해 새 설정 반영.
                                ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "
                                    cd ${remoteDir} && \\
                                    docker compose up -d --remove-orphans && \\
                                    docker compose restart prometheus
                                "
                            """
                        }
                        echo "모니터링 스택 배포 완료 — Prometheus :9090, Grafana :3001, Node Exporter :9100"
                    } catch (Exception e) {
                        echo "STAGE_ERROR: ${e.getMessage()}"
                        throw e
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
            script {
                // 1. 최근 빌드 로그 150줄 추출
                def rawLog = currentBuild.rawBuild.getLog(150).join('\n')

                // 2. Groq API 요청 데이터를 Map 객체로 생성
                def requestMap = [
                    model: "llama-3.3-70b-versatile",
                    messages: [
                        [
                            role: "user",
                            content: "너는 시니어 DevOps 엔지니어이다. 다음 Jenkins 빌드 에러 로그를 분석해서 원인을 파악하고, 구체적인 해결책을 한국어로 제시해줘.\n\n[빌드 로그]\n" + rawLog
                        ]
                    ]
                ]
                
                // Pipeline Utility Steps 플러그인의 writeJSON을 쓰면 특수문자/줄바꿈 이스케이프가 완벽히 처리됨 (JSON 파싱 에러 원천 차단)
                writeJSON file: 'groq_request.json', json: requestMap
                
                // 기본 응답 메시지 (API 호출 실패 대비)
                env.AI_ANALYSIS = "AI 분석을 가져오는 중 오류가 발생했거나 대기 시간이 초과되었습니다."

                try {
                    withCredentials([string(credentialsId: 'GROQ_API_KEY', variable: 'GROQ_API_KEY')]) {
                        // 3. curl로 API 호출 (API 키는 보안을 위해 쉘 환경변수로 전달, 작은따옴표 3개 사용으로 Groovy 변수 보간 방지)
                        sh '''
                            curl -sf --max-time 30 --connect-timeout 10 \
                                 -X POST "https://api.groq.com/openai/v1/chat/completions" \
                                 -H "Authorization: Bearer $GROQ_API_KEY" \
                                 -H "Content-Type: application/json" \
                                 -d @groq_request.json \
                                 -o groq_response.json
                        '''
                        
                        // 4. Pipeline Utility Steps의 readJSON을 사용해 응답 파싱
                        def jsonResponse = readJSON file: 'groq_response.json'
                        if (jsonResponse.choices && jsonResponse.choices[0] && jsonResponse.choices[0].message) {
                            env.AI_ANALYSIS = jsonResponse.choices[0].message.content
                        } else {
                            def rawResponse = sh(script: 'cat groq_response.json', returnStdout: true).trim()
                            env.AI_ANALYSIS = "AI 분석 실패 (Groq API 응답 구조 오류):\n${rawResponse}"
                        }
                    }
                } catch (Exception e) {
                    env.AI_ANALYSIS = "API 통신 또는 파싱 오류 발생: ${e.getMessage()}"
                }
            }

            emailext (
                subject: "❌ [Jenkins] 빌드 실패 및 AI 원인 분석: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: """<div style="font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;">
                             <h2>❌ 빌드 중 에러가 발생했습니다.</h2>
                             <p><b>Job:</b> ${env.JOB_NAME}<br>
                             <b>Build Number:</b> ${env.BUILD_NUMBER}<br>
                             <b>Console Log:</b> <a href="${env.BUILD_URL}console">${env.BUILD_URL}console</a></p>
                             <hr>
                             <h3>🤖 Groq AI의 에러 분석 및 해결 제안</h3>
                             <pre style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; white-space: pre-wrap; font-family: inherit; font-size: 14px;">${env.AI_ANALYSIS.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')}</pre>
                         </div>""",
                to: 'kjyyoung0305@gmail.com, yooncy0511@gmail.com, lee.moonjeong@gmail.com, wq0212@naver.com',
                mimeType: 'text/html'
            )
        }
        always {
            echo "Pipeline 완료 — 브랜치: ${env.DEPLOY_BRANCH}"
        }
    }
}
