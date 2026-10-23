// Pipeline CI/CD de Artemis
// Estrategia de ramas (GitFlow simplificado):
//   feature/*  -> build + lint + tests
//   develop    -> + analisis de seguridad (bandit)
//   main       -> + analisis de seguridad + empaquetado/entrega del artefacto
def ci  // modulo reutilizable: ci/pipeline-utils.groovy

pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        disableConcurrentBuilds(abortPrevious: true)
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }

    environment {
        DB_ENGINE         = 'sqlite'
        DEBUG             = 'False'
        DJANGO_SECRET_KEY = 'jenkins-ci-only'
        GITHUB_REPO       = 'EnzoCortez/artemis_scaffold_ci'
        PIP_CACHE_DIR     = "${JENKINS_HOME}/cache/pip"
        LINT_MAX          = '454'  // linea base de flake8: no se admiten violaciones nuevas
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    def scmVars = checkout scm
                    env.GIT_COMMIT = scmVars.GIT_COMMIT
                    ci = load 'ci/pipeline-utils.groovy'
                    ci.githubStatus('pending', 'Pipeline en ejecucion')
                    env.SOLO_DOCS = ci.soloCambiosDeDocumentacion() ? 'true' : 'false'
                }
                sh 'git log -1 --pretty="Commit: %h - %s (%an)"'
            }
        }

        stage('Build') {
            steps {
                script { env.VENV = ci.prepararEntorno() }
            }
        }

        stage('Calidad y pruebas') {
            // Ejecucion selectiva: un commit que solo cambia documentacion no re-ejecuta el analisis
            when { expression { env.SOLO_DOCS != 'true' } }
            failFast true
            parallel {
                stage('Lint (flake8)') {
                    steps { script { ci.lint(Integer.parseInt(env.LINT_MAX)) } }
                }
                stage('Tests unitarios') {
                    steps { script { ci.tests() } }
                }
                stage('Seguridad (bandit)') {
                    when { anyOf { branch 'main'; branch 'develop' } }
                    steps { script { ci.seguridad() } }
                }
            }
        }

        stage('Entrega') {
            when { branch 'main' }
            steps { script { ci.empaquetar() } }
        }
    }

    post {
        always   { script { if (ci != null) { ci.publicarReportes() } } }
        success  { script { if (ci != null) { ci.notificar('EXITOSO') } } }
        unstable { script { if (ci != null) { ci.notificar('INESTABLE') } } }
        failure  { script { if (ci != null) { ci.notificar('FALLIDO') } } }
        aborted  { script { if (ci != null) { ci.notificar('ABORTADO') } } }
        cleanup  { deleteDir() }
    }
}
