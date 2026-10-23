// Funciones reutilizables del pipeline de Artemis.
// Se cargan desde el Jenkinsfile con: ci = load 'ci/pipeline-utils.groovy'

// Build con cache: un virtualenv por hash de dependencias, compartido entre builds y ramas
def prepararEntorno() {
    def clave = sh(returnStdout: true,
                   script: 'cat requirements.txt requirements-ci.txt | sha256sum | cut -c1-12').trim()
    def venv = "${env.JENKINS_HOME}/cache/venv-${clave}"
    sh """
        if [ -x "${venv}/bin/python" ]; then
            echo "Cache HIT: reutilizando ${venv}"
        else
            echo "Cache MISS: creando ${venv}"
            mkdir -p "${env.JENKINS_HOME}/cache"
            TMP="${venv}.tmp-\$\$"
            python3 -m venv "\$TMP"
            "\$TMP/bin/python" -m pip install --quiet --upgrade pip
            "\$TMP/bin/python" -m pip install --quiet -r requirements.txt -r requirements-ci.txt
            mv -T "\$TMP" "${venv}" 2>/dev/null || rm -rf "\$TMP"
        fi
        "${venv}/bin/python" -m compileall -q artemis_project ioc_manager
        "${venv}/bin/python" manage.py check
    """
    return venv
}

// Linter con quality gate: el build queda INESTABLE si aparecen violaciones nuevas
def lint(int maximo) {
    sh 'mkdir -p reports && "$VENV/bin/python" -m flake8 --exit-zero --output-file=reports/flake8.txt .'
    int total = Integer.parseInt(sh(returnStdout: true, script: 'wc -l < reports/flake8.txt').trim())
    env.LINT_TOTAL = "${total}"
    if (total > maximo) {
        unstable("Quality gate flake8: ${total} violaciones (maximo permitido ${maximo})")
    } else {
        echo "Quality gate flake8 OK: ${total} violaciones (maximo permitido ${maximo})"
    }
}

def tests() {
    sh '''
        "$VENV/bin/python" manage.py test ioc_manager -v 2 \
            --testrunner xmlrunner.extra.djangotestrunner.XMLTestRunner
    '''
}

// Analisis de seguridad: falla el build ante hallazgos de severidad media o alta
def seguridad() {
    sh '''
        mkdir -p reports
        "$VENV/bin/python" -m bandit -q -r artemis_project ioc_manager \
            -x "*/migrations/*,*/tests.py" -ll -f txt -o reports/bandit.txt \
            || { cat reports/bandit.txt; exit 1; }
        echo "bandit: sin hallazgos de severidad media/alta"
    '''
}

// Entrega: artefacto versionado con el codigo de la aplicacion
def empaquetar() {
    def version = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.substring(0, 7)}"
    sh """
        mkdir -p dist
        git archive --format=zip -o dist/artemis-${version}.zip HEAD \
            artemis_project ioc_manager manage.py requirements.txt run_waitress.py web.config
    """
    archiveArtifacts artifacts: 'dist/*.zip', fingerprint: true
}

def publicarReportes() {
    junit allowEmptyResults: true, testResults: 'test-reports/*.xml'
    archiveArtifacts allowEmptyArchive: true, artifacts: 'reports/**'
}

// Devuelve true si el ultimo commit solo modifica documentacion (docs/ o archivos .md)
def soloCambiosDeDocumentacion() {
    def cambios = sh(returnStdout: true, script: 'git diff --name-only HEAD~1 HEAD 2>/dev/null || true').trim()
    if (!cambios) {
        return false
    }
    for (String archivo : cambios.split('\n')) {
        if (!(archivo.startsWith('docs/') || archivo.endsWith('.md'))) {
            return false
        }
    }
    echo 'Solo hay cambios de documentacion: se omite la etapa de calidad y pruebas'
    return true
}

// Notificacion a GitHub: marca el commit con el estado del pipeline (commit status)
def githubStatus(String estado, String descripcion) {
    if (!env.GIT_COMMIT) {
        return
    }
    withCredentials([usernamePassword(credentialsId: 'github-pat',
                                      usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
        withEnv(["GH_STATE=${estado}", "GH_DESC=${descripcion}"]) {
            sh '''
                curl -sS -o /dev/null -w "GitHub commit status: HTTP %{http_code}\\n" -X POST \
                    -H "Authorization: Bearer ${GH_TOKEN}" \
                    -H "Accept: application/vnd.github+json" \
                    "https://api.github.com/repos/${GITHUB_REPO}/statuses/${GIT_COMMIT}" \
                    -d "{\\"state\\":\\"${GH_STATE}\\",\\"context\\":\\"jenkins/artemis-ci\\",\\"description\\":\\"${GH_DESC}\\",\\"target_url\\":\\"${BUILD_URL}\\"}"
            '''
        }
    }
}

def telegram(String estado) {
    def iconos = [EXITOSO: '✅', FALLIDO: '❌', INESTABLE: '⚠️', ABORTADO: '⏹️']
    def commit = env.GIT_COMMIT ? env.GIT_COMMIT.substring(0, 7) : 'n/a'
    def mensaje = "${iconos[estado]} Pipeline ${estado}\n" +
                  "Job: ${env.JOB_NAME}\n" +
                  "Rama: ${env.BRANCH_NAME ?: 'n/a'}\n" +
                  "Commit: ${commit}\n" +
                  "Build: #${env.BUILD_NUMBER}\n" +
                  "Lint: ${env.LINT_TOTAL ?: 'omitido'} violaciones\n" +
                  "Duracion: ${currentBuild.durationString.replace(' and counting', '')}\n" +
                  "${env.BUILD_URL}"
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

def notificar(String estado) {
    def estadosGithub = [EXITOSO: 'success', INESTABLE: 'failure', FALLIDO: 'failure', ABORTADO: 'error']
    githubStatus(estadosGithub[estado], "Build #${env.BUILD_NUMBER} ${estado.toLowerCase()}")
    telegram(estado)
}

return this
