# Pipeline de entrega continua – Estrategias de optimización

## Estrategia de branching (GitFlow simplificado)

| Rama | Propósito | Etapas que corren |
|------|-----------|-------------------|
| `feature/*` | Desarrollo de una funcionalidad | Checkout → Build → Lint ‖ Tests |
| `develop` | Integración del equipo | Checkout → Build → Lint ‖ Tests ‖ Seguridad |
| `main` | Producción / release | Checkout → Build → Lint ‖ Tests ‖ Seguridad → **Entrega** |

Flujo: `feature/*` → Pull Request → `develop` → Pull Request → `main`.

## Etapas

| Etapa | Herramienta | Criterio |
|-------|-------------|----------|
| Checkout | Git (repo privado, credencial `github-pat`) | — |
| Build | `pip`, `compileall`, `manage.py check` | Falla si el código no compila o la configuración es inválida |
| Lint | **flake8** (`.flake8`) | *Quality gate*: build **INESTABLE** si hay más violaciones que la línea base (`LINT_MAX = 454`) |
| Tests | Django test + JUnit | Falla si algún test falla |
| Seguridad | **bandit** | Falla ante hallazgos de severidad media/alta |
| Entrega | `git archive` + `archiveArtifacts` | Solo `main`: artefacto `artemis-<build>-<commit>.zip` |

## Post

| Condición | Acción |
|-----------|--------|
| `always` | Publica reportes JUnit y archiva `reports/` (flake8, bandit) |
| `success` | Commit status **success** en GitHub + Telegram ✅ |
| `unstable` | Commit status **failure** en GitHub + Telegram ⚠️ |
| `failure` | Commit status **failure** en GitHub + Telegram ❌ |
| `aborted` | Commit status **error** en GitHub + Telegram ⏹️ |
| `cleanup` | Limpia el workspace (`deleteDir`) |

Al iniciar, el pipeline marca el commit como **pending** en GitHub.

## Optimizaciones

1. **Ejecución paralela**: Lint, Tests y Seguridad corren en `parallel` con `failFast true`.
2. **Caché**:
   - Virtualenv cacheado en `$JENKINS_HOME/cache/venv-<hash>`; el hash se calcula de `requirements.txt` + `requirements-ci.txt`. Si las dependencias no cambian, el build no reinstala nada (*Cache HIT*).
   - Caché de descargas de pip en `$JENKINS_HOME/cache/pip`.
3. **Ejecución selectiva**:
   - Por rama: `when { branch 'main' }` / `anyOf { branch 'main'; branch 'develop' }`.
   - Por cambios: si el último commit solo toca `docs/` o `*.md`, se omite "Calidad y pruebas".
   - `disableConcurrentBuilds(abortPrevious: true)`: un push nuevo cancela el build anterior de la misma rama.
4. **Pipelines modulares y reutilizables**: la lógica vive en `ci/pipeline-utils.groovy` (funciones `prepararEntorno`, `lint`, `tests`, `seguridad`, `empaquetar`, `notificar`, `githubStatus`, `telegram`), que el `Jenkinsfile` carga con `load`. El Jenkinsfile solo orquesta las etapas.

## Configuración en Jenkins

1. **Token de GitHub**: editar el token `jenkins-artemis` → *Repository permissions* → **Commit statuses: Read and write** (además de *Contents: Read-only*). Si se regenera el token, actualizar la credencial `github-pat`.
2. **Nueva Tarea** → `artemis-cd` → **Multibranch Pipeline**.
3. *Branch Sources* → **Add source → Git**:
   - Project Repository: `https://github.com/EnzoCortez/artemis_scaffold_ci.git`
   - Credentials: `github-pat`
   - Behaviours: *Discover branches*
4. *Build Configuration*: by Jenkinsfile, Script Path `Jenkinsfile`.
5. *Scan Multibranch Pipeline Triggers*: **Periodically if not otherwise run** → 2 minutes (Jenkins está en `localhost`, GitHub no puede enviarle webhooks).
6. **Guardar**: Jenkins detecta las ramas que tienen `Jenkinsfile` y crea un job por cada una.

## Demostraciones sugeridas

| Demo | Cómo | Qué se observa |
|------|------|----------------|
| Paralelo + seguridad | Build de `develop` | Lint, Tests y Seguridad en paralelo; ✔ en GitHub |
| Caché | Volver a ejecutar `develop` | Log "Cache HIT" y build más corto |
| Selectiva por rama | Build de `feature/demo-docs` | Sin etapa Seguridad ni Entrega |
| Selectiva por cambios | Mismo build de `feature/demo-docs` (solo cambia docs) | "Calidad y pruebas" omitida |
| Entrega | PR `develop` → `main`, merge | Etapa Entrega y artefacto `.zip` |
| Quality gate | Agregar código con errores de estilo en una feature | Build ⚠️ INESTABLE |

## Historial

- Rama `feature/demo-docs`: commit que solo modifica documentación, usado para demostrar la ejecución selectiva.
