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
        TARGET_USER   = "sogang018"
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

        stage('Deploy to k3s') {
            steps {
                script {
                    try {
                        sshagent(["${SSH_CRED_ID}"]) {
                            sh """
                                # k8s 매니페스트 전송
                                ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "mkdir -p ~/boonpick/k8s"
                                scp -r -o StrictHostKeyChecking=no k8s/ ${TARGET_USER}@${TARGET_SERVER}:~/boonpick/

                                ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "
                                    kubectl create namespace boonpick --dry-run=client -o yaml | kubectl apply -f -

                                    # Secret 생성/갱신 (--dry-run=client로 덮어쓰기 안전 처리)
                                    kubectl create secret generic boonpick-secret \\
                                        --namespace=boonpick \\
                                        --from-literal=DB_HOST='${env.DB_HOST}' \\
                                        --from-literal=DB_USER='${env.DB_USER}' \\
                                        --from-literal=DB_PASSWORD='${env.DB_PASSWORD}' \\
                                        --from-literal=SAINT_ID='${env.SAINT_ID}' \\
                                        --from-literal=SAINT_PW='${env.SAINT_PW}' \\
                                        --from-literal=SMTP_USER='${env.SMTP_USER}' \\
                                        --from-literal=SMTP_PASSWORD='${env.SMTP_PASSWORD}' \\
                                        --dry-run=client -o yaml | kubectl apply -f -

                                    # ConfigMap, Service, CronJob 적용
                                    kubectl apply -f ~/boonpick/k8s/

                                    # 빌드별 이미지 태그 고정 (RollingUpdate 트리거)
                                    kubectl set image deployment/boonpick-backend \\
                                        boonpick-backend=${IMAGE_NAME}:${env.IMAGE_TAG}
                                    # kubectl set image deployment/boonpick-frontend \\
                                    #    boonpick-frontend=${DOCKER_HUB_USER}/boonpick-frontend:latest
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

        stage('Rollout Status') {
            steps {
                script {
                    try {
                        sshagent(["${SSH_CRED_ID}"]) {
                            sh """
                                ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "
                                    kubectl rollout status deployment/boonpick-backend --timeout=120s
                                    # kubectl rollout status deployment/boonpick-frontend --timeout=120s
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
                                # Grafana 자동 프로비저닝(데이터소스+부하테스트 대시보드) 전송
                                scp -r -o StrictHostKeyChecking=no grafana \\
                                    ${TARGET_USER}@${TARGET_SERVER}:${remoteDir}/

                                # 2) 컨테이너 기동(또는 설정 갱신). prometheus는 재시작해 새 설정 반영.
                                # 운영 서버에 docker compose v2(plugin) 또는 v1(docker-compose) 둘 중
                                # 무엇이 있는지 자동 감지. \$는 원격 셸 변수이므로 Groovy 보간을 막기 위해 escape.
                                ssh -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_SERVER} "
                                    set -e
                                    cd ${remoteDir}
                                    if command -v docker-compose >/dev/null 2>&1; then
                                        COMPOSE='docker-compose'
                                    elif docker compose version >/dev/null 2>&1; then
                                        COMPOSE='docker compose'
                                    else
                                        echo 'ERROR: neither docker-compose nor docker compose plugin is installed on the target server' >&2
                                        exit 127
                                    fi
                                    echo \\\"Using: \\\$COMPOSE\\\"
                                    # KeyError: 'ContainerConfig' (compose v1 의 in-place 재생성 버그) 회피:
                                    # down 후 up 으로 깔끔히 재생성. 모니터링이라 짧은 재기동 허용,
                                    # grafana-data 등 named volume 은 down 으로 삭제되지 않아 유지됨.
                                    \\\$COMPOSE down --remove-orphans || true
                                    \\\$COMPOSE up -d
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
        echo "빌드 성공 — 이메일 알림 비활성화됨"
    }

    failure {
        echo "빌드 실패 — 이메일/Groq AI 알림 비활성화됨"
    }

    always {
        echo "Pipeline 완료 — 브랜치: ${env.DEPLOY_BRANCH}"
    }
    }
}
