// Pipeline CI de Artemis
// Etapas: 1) Integracion con el repo privado  2) Compilacion y tests  3) Notificacion (Telegram)
pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    environment {
        DB_ENGINE         = 'sqlite'
        DEBUG             = 'False'
        DJANGO_SECRET_KEY = 'jenkins-ci-only'
        VENV              = "${WORKSPACE}/.venv"
    }

    stages {
        stage('1. Integracion repo privado') {
            steps {
                // Usa la URL y la credencial (PAT de GitHub) configuradas en el job
                checkout scm
                sh 'git log -1 --pretty="Commit: %h - %s (%an)"'
            }
        }

        stage('2. Compilacion y tests') {
            steps {
                sh '''
                    python3 -m venv "$VENV"
                    . "$VENV/bin/activate"
                    pip install --quiet --upgrade pip
                    pip install --quiet -r requirements.txt unittest-xml-reporting

                    # "Compilacion": byte-compila el codigo y valida la configuracion de Django
                    python -m compileall -q artemis_project ioc_manager
                    python manage.py check

                    # Tests automatizados con reporte JUnit
                    python manage.py test ioc_manager -v 2 \
                        --testrunner xmlrunner.extra.djangotestrunner.XMLTestRunner
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'test-reports/*.xml'
                }
            }
        }
    }

    // 3. Notificacion de ejecucion exitosa o fallida
    post {
        success { script { notifyTelegram('EXITOSO') } }
        failure { script { notifyTelegram('FALLIDO') } }
        unstable { script { notifyTelegram('INESTABLE') } }
    }
}

def notifyTelegram(String estado) {
    def icono = [EXITOSO: '✅', FALLIDO: '❌', INESTABLE: '⚠️'][estado]
    def mensaje = "${icono} Pipeline ${estado}\nJob: ${env.JOB_NAME}\nBuild: #${env.BUILD_NUMBER}\nDuracion: ${currentBuild.durationString.replace(' and counting', '')}\n${env.BUILD_URL}"
    withCredentials([
        string(credentialsId: 'telegram-bot-token', variable: 'TG_TOKEN'),
        string(credentialsId: 'telegram-chat-id', variable: 'TG_CHAT')
    ]) {
        withEnv(["TG_MSG=${mensaje}"]) {
            sh '''
                curl -sS -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
                    --data-urlencode "chat_id=${TG_CHAT}" \
                    --data-urlencode "text=${TG_MSG}" > /dev/null
            '''
        }
    }
}
