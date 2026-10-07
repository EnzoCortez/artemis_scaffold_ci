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
    *   **IMPORTANTE**: No copie la carpeta `venv` si ya existe. Si la copia, bórrela en el destino antes de continuar, ya que los entornos virtuales no son "portables".
2.  Abra PowerShell como Administrador y navegue a esa carpeta.
3.  Cree el entorno virtual e instale dependencias:
    ```powershell
    cd C:\inetpub\wwwroot\Artemis
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    pip install waitress
    ```

4.  **Configurar base de datos y credenciales seguras (AES-GCM)**:
    *   **NO** cree el archivo `.env` manualmente con contraseñas en texto plano.
    *   Ejecute el script de generación de credenciales:
        ```powershell
        python setup_aes_gcm.py
        ```
    *   El script le solicitará el **Usuario** y la **Contraseña** de la base de datos.
    *   Copie los valores generados (que se mostrarán en pantalla) a un nuevo archivo `.env` en la raíz:
        ```ini
        DEBUG=False
        ALLOWED_HOSTS=*
        DB_ENGINE=mssql
        DB_NAME=artemis_prod
        DB_HOST=DBSRV7
        
        # Credenciales Cifradas (Generadas por setup_aes_gcm.py)
        DB_ENCRYPTION_KEY=...
        DB_USER_ENCRYPTED=...
        DB_PASSWORD_ENCRYPTED=...
        
        # Seguridad Django (Generada por setup_aes_gcm.py)
        DJANGO_SECRET_KEY=...
        ```

5.  **Inicialización y Superusuario**:
    ```powershell
    # 1. Aplicar migraciones
    python manage.py migrate

    # 2. Recolectar estáticos
    python manage.py collectstatic --noinput

    # 3. Crear Superusuario Local (Política de Admin Único)
    python manage.py createsuperuser --username=admin_local
    ```

---

## Paso 3: Configurar el Servicio de Windows (usando WinSW)

La aplicación correrá en puerto 8090 en segundo plano.

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
    
    *Verifique en navegador que `http://localhost:8090` responde.*
    *Para ver logs, revise los archivos `.log` que se crearán en la misma carpeta.*

---

## Paso 4: Configurar IIS Website

1.  En IIS Manager, cree un nuevo **Website** (o modifique "Default Web Site").
    *   **Site Name**: Artemis
    *   **Physical Path**: `C:\inetpub\wwwroot\Artemis`
    *   **Binding**: Port 80.
2.  Asegúrese de que el archivo `web.config` incluido en el proyecto esté en la carpeta raíz. Este archivo le dice a IIS que reenvíe todo a `http://localhost:8090`.

**Referencia de web.config:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <rule name="ReverseProxyToWaitress" stopProcessing="true">
                    <match url="(.*)" />
                    <action type="Rewrite" url="http://localhost:8090/{R:1}" />
                </rule>
            </rules>
        </rewrite>
    </system.webServer>
</configuration>
```

## Paso 5: Firewall y Acceso Remoto

### 5.1 Abrir Puerto 80
Para que otros dispositivos puedan ver la página, debe permitir el tráfico HTTP en el Firewall de Windows.
Ejecute este comando en **PowerShell (como Administrador)**:

```powershell
New-NetFirewallRule -DisplayName "Artemis Web" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow
```

### 5.2 Conectarse desde otro dispositivo
1.  Averigüe la dirección IP del servidor. En PowerShell ejecute:
    ```powershell
    ipconfig
    ```
    Busque la dirección IPv4 (ejemplo: `192.168.1.15` o `10.0.0.5`).

2.  Desde cualquier computadora o celular conectado a la misma red, abra el navegador e ingrese:
    `http://<DIRECCION_IP_DEL_SERVIDOR>`
    
    Ejemplo: `http://192.168.1.15`

Si ve la pantalla de Login de Artemis, ¡todo ha sido un éxito!

---

## 6. Mantenimiento y Ciclo de Vida

### 6.1 Garantía de Disponibilidad (Auto-Restart)
El servicio **ArtemisService** está configurado para operar como un servicio crítico de Windows. 
*   **Inicio Automático:** Se inicia con el sistema operativo sin necesidad de logueo de usuario.
*   **Restaura ante Fallos:** Si la aplicación crashea, el wrapper (WinSW) intentará reiniciarla automáticamente tras 10 segundos, y nuevamente tras 20 segundos si falla de nuevo.
*   **Logs:** Cualquier error de arranque o crash quedará registrado en `ArtemisService.out.log` y `ArtemisService.err.log` en el directorio raíz.

### 6.2 Actualización de Dependencias (Modo Offline)
Dado que el servidor NO tiene internet, las actualizaciones de librerías Python deben seguir este flujo estricto:

1.  **En Equipo con Internet:**
    Descargar los paquetes (`wheels`) y sus dependencias:
    ```powershell
    # Ejemplo: Actualizar Django
    mkdir offline_packages
    pip download Django==5.2.11 -d offline_packages
    ```
2.  **Escaneo de Seguridad:**
    Analizar la carpeta `offline_packages` con antivirus corporativo antes de moverla.
3.  **Transferencia:**
    Copiar la carpeta `offline_packages` al servidor (`C:\inetpub\wwwroot\Artemis\packages`).
4.  **Instalación Offline:**
    ```powershell
    cd C:\inetpub\wwwroot\Artemis
    .\venv\Scripts\activate
    pip install --no-index --find-links=./packages Django
    ```
5.  **Reinicio de Servicio:**
    Para aplicar cambios:
    ```powershell
    .\ArtemisService.exe restart
    ```
