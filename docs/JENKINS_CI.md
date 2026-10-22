# Pipeline CI con Jenkins – Artemis

Pipeline declarativo (`Jenkinsfile` en la raíz) con 3 etapas:

| # | Etapa | Qué hace |
|---|-------|----------|
| 1 | **Integración repo privado** | `checkout scm` del repo privado de GitHub usando un Personal Access Token guardado como credencial de Jenkins. |
| 2 | **Compilación y tests** | Crea un virtualenv, instala `requirements.txt`, byte-compila el código (`compileall`), valida Django (`manage.py check`) y ejecuta los tests unitarios con reporte JUnit. Usa SQLite (`DB_ENGINE=sqlite`) para no depender de SQL Server. |
| 3 | **Notificación** | Bloque `post`: envía un mensaje a Telegram indicando si el build fue EXITOSO, FALLIDO o INESTABLE, con el número de build, la duración y el enlace. |

---

## 1. Levantar Jenkins con Docker

```bash
cd jenkins
docker compose up -d --build
docker exec jenkins-artemis cat /var/jenkins_home/secrets/initialAdminPassword
```

Abrir <http://localhost:8080>, pegar la contraseña, elegir **Install suggested plugins** y crear el usuario admin.
La imagen (`jenkins/Dockerfile`) ya incluye Python 3, `venv`, `curl` y los plugins de `jenkins/plugins.txt`.

## 2. Credencial para el repo privado (GitHub)

1. GitHub → *Settings → Developer settings → Personal access tokens → Fine-grained tokens* → **Generate new token**.
   - Repository access: *Only select repositories* → `artemis_scaffold`.
   - Permissions: **Contents: Read-only**.
2. Jenkins → *Manage Jenkins → Credentials → System → Global credentials → Add Credentials*:
   - Kind: **Username with password**
   - Username: tu usuario de GitHub
   - Password: el token
   - ID: `github-pat`

## 3. Bot de Telegram (notificaciones)

1. En Telegram, hablar con **@BotFather** → `/newbot` → copiar el **token**.
2. Enviar cualquier mensaje a tu bot y abrir
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → copiar `"chat":{"id": ...}`.
3. En Jenkins crear dos credenciales de tipo **Secret text**:
   - ID `telegram-bot-token` → el token del bot
   - ID `telegram-chat-id` → el chat id

## 4. Crear el job

1. *New Item* → nombre `artemis-ci` → **Pipeline** → OK.
2. Sección **Pipeline**:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `https://github.com/EnzoCortez/artemis_scaffold.git`
   - Credentials: `github-pat`
   - Branch: `*/claude/gifted-goldberg-8fx0jg` (o `*/main` tras hacer merge)
   - Script Path: `Jenkinsfile`
3. (Opcional) *Build Triggers* → **Poll SCM** con `H/5 * * * *` para que corra solo con cada push.
4. **Save** → **Build Now**.

## 5. Evidencias para la entrega

- Captura del **Stage View** con las 3 etapas en verde.
- Captura de **Test Result** (10 tests OK).
- Captura del mensaje ✅ en Telegram.
- Para demostrar la notificación de fallo: romper un test a propósito (p. ej. cambiar un valor esperado en `ioc_manager/tests.py`), hacer push, ejecutar y capturar el ❌; luego revertir.
- Captura de la configuración del repo en GitHub mostrando que es **Private**.

## Ejecutar los tests en local

```bash
DB_ENGINE=sqlite python manage.py test ioc_manager -v 2
```
