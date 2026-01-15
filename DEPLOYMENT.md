# Guía de Despliegue: Artemis en Windows Server 2019

Esta guía detalla los pasos para desplegar la aplicación "Artemis" en un servidor Windows Server 2019 utilizando **IIS** como servidor web (Reverse Proxy) y **Waitress** como servidor de aplicaciones WSGI.

## Prerrequisitos y Descargas

Antes de comenzar, asegúrese de descargar e instalar los siguientes componentes en el servidor:

1.  **Python 3.11+**
    *   Descarga: [Python 3.11.x Windows Installer (64-bit)](https://www.python.org/downloads/windows/)
    *   *Nota: Al instalar, marque la casilla "Add Python to PATH".*

2.  **ODBC Driver for SQL Server**
    *   Necesario para la conexión a base de datos.
    *   Descarga: [ODBC Driver 17 for SQL Server](https://go.microsoft.com/fwlink/?linkid=2262330) (o versión 18).

3.  **IIS URL Rewrite Module 2.1**
    *   Necesario para que IIS reenvíe peticiones a Waitress.
    *   Descarga: [URL Rewrite Module 2.1](https://www.iis.net/downloads/microsoft/url-rewrite)

4.  **Application Request Routing (ARR) 3.0**
    *   Necesario para la funcionalidad de Reverse Proxy.
    *   Descarga: [Application Request Routing 3.0](https://www.iis.net/downloads/microsoft/application-request-routing)

5.  **WinSW (Windows Service Wrapper)**
    *   Alternativa robusta a NSSM (ya que el sitio oficial suele estar caído).
    *   Descarga: [WinSW v2.12.0 (o superior)](https://github.com/winsw/winsw/releases)
    *   Descargue el archivo `WinSW-x64.exe`.

---

## Paso 1: Preparación del Entorno IIS

### 1.1 Habilitar Proxy en ARR
1.  Abra **IIS Manager**.
2.  Haga clic en el nombre del servidor (nodo raíz en la izquierda).
3.  Abra **Application Request Routing Cache**.
4.  En el panel derecho ("Actions"), clic en **Server Proxy Settings**.
5.  Marque la casilla **Enable proxy**.
6.  Clic en **Apply**.

---

## Paso 2: Instalación de la Aplicación

1.  Copie la carpeta `artemis_scaffold` a `C:\inetpub\wwwroot\Artemis` (o ruta de preferencia).
2.  Abra PowerShell como Administrador y navegue a esa carpeta.
3.  Cree el entorno virtual e instale dependencias:
    ```powershell
    cd C:\inetpub\wwwroot\Artemis
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    pip install waitress
    pip install mssql-django pyodbc
    ```

4.  **Configurar base de datos**:
    *   Cree un archivo `.env` en la raíz (si no existe) basado en sus credenciales de SQL Server.
    *   Ejemplo:
        ```ini
        DEBUG=False
        ALLOWED_HOSTS=*
        DB_ENGINE=mssql
        DB_NAME=artemis_prod
        DB_USER=sa
        DB_PASS=SuContraseña
        DB_HOST=LOCALHOST\SQLEXPRESS
        ```

5.  **Recopilar estáticos**:
    ```powershell
    python manage.py collectstatic --noinput
    ```

---

## Paso 3: Configurar el Servicio de Windows (usando WinSW)

La aplicación correrá en puerto 8080 en segundo plano.

1.  Mueva el archivo `WinSW-x64.exe` descargado a la carpeta del proyecto: `C:\inetpub\wwwroot\Artemis`.
2.  Renómbrelo a **`ArtemisService.exe`**.
3.  Asegúrese de que el archivo de configuración `ArtemisService.xml` (generado en el proyecto) esté en la misma carpeta.
    *   Este archivo ya apunta a `venv\Scripts\python.exe` y `run_waitress.py`.

4.  Instalar el servicio:
    Abra PowerShell como Administrador en esa carpeta y ejecute:
    ```powershell
    .\ArtemisService.exe install
    ```

5.  Iniciar el servicio:
    ```powershell
    .\ArtemisService.exe start
    ```
    
    *Verifique en navegador que `http://localhost:8080` responde.*
    *Para ver logs, revise los archivos `.log` que se crearán en la misma carpeta.*

---

## Paso 4: Configurar IIS Website

1.  En IIS Manager, cree un nuevo **Website** (o modifique "Default Web Site").
    *   **Site Name**: Artemis
    *   **Physical Path**: `C:\inetpub\wwwroot\Artemis`
    *   **Binding**: Port 80.
2.  Asegúrese de que el archivo `web.config` incluido en el proyecto esté en la carpeta raíz. Este archivo le dice a IIS que reenvíe todo a `http://localhost:8080`.

**Referencia de web.config:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <rule name="ReverseProxyToWaitress" stopProcessing="true">
                    <match url="(.*)" />
                    <action type="Rewrite" url="http://localhost:8080/{R:1}" />
                </rule>
            </rules>
        </rewrite>
    </system.webServer>
</configuration>
```

## Paso 5: Firewall
1.  Asegúrese de abrir el puerto 80 (o 443 si usa SSL) en el **Windows Defender Firewall** para permitir el tráfico externo.
