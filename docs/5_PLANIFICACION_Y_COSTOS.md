## 5. Planificación y costos del proyecto

Dado que el enfoque seleccionado para la ejecución de este proyecto es la **metodología ágil (Scrum)**, la planificación se estructura en base a la definición del Backlog del Producto, un plan de releases distribuido en *Sprints* iterativos, y una estrategia de integración y despliegue continuo (CI/CD).

### 5.1. Product Backlog

El alcance del proyecto se ha descompuesto en 6 Fases de Implementación principales, de las cuales se desprenden las Tareas (T) específicas del Backlog:

| Fase de Implementación | ID | Nombre de la Tarea | Descripción / Entregable |
| :--- | :--- | :--- | :--- |
| **1. Ingeniería y Arquitectura** | T-1.1 | Reglas de Negocio | Definición de flujos y requisitos del sistema. |
| | T-1.2 | Modelado de BD | Diagramas y creación de la Base de Datos en SQL Server. |
| | T-1.3 | Diseño C4 | Planos arquitectónicos de contenedores y contexto. |
| **2. Entorno y Configuración** | T-2.1 | Repositorios Git | Configuración de control de versiones y entornos virtuales. |
| | T-2.2 | Conexión ODBC | Configuración de enlaces entre Django y la base de datos. |
| | T-2.3 | Configuración de Django | Creación de esqueleto del proyecto y variables de entorno. |
| **3. Construcción del Backend** | T-3.1 | Motor Ingesta/Regex | Procesamiento de texto plano y clasificación analítica. |
| | T-3.2 | Fragmentación de algoritmo | Lógica para evasión de Timeouts en grandes inyecciones ACID. |
| | T-3.3 | API de Estados | Lógica transaccional para modificar el estado de los IoCs. |
| **4. Desarrollo de Frontend** | T-4.1 | Diseño UI/UX | Maquetado visual de la plataforma. |
| | T-4.2 | Analistas de panel | Vistas de tablas dinámicas para el control de la inteligencia. |
| | T-4.3 | Empaquetador ZIP | Motor de compilación para la exportación de archivos curados. |
| **5. Pruebas y Calidad (QA)** | T-5.1 | Pruebas Unitarias | Testeo de código individual. |
| | T-5.2 | Pruebas de Estrés | Test de rendimiento y concurrencia (>150k registros). |
| | T-5.3 | Aceptación (UAT) | Simulacro de uso real con el cliente final (Equipo SOC). |
| | T-5.4 | Desarrollo documentación | Establecimiento, validación y entrega formal de documentación (Guía de usuario, etc.). |
| **6. Pase a Producción** | T-6.1 | Despliegue | Alojamiento y despliegue del proyecto en Windows Server. |
| | T-6.2 | Publicación de listas | Implementación de listas de diseminación de IoCs. |
| | T-6.3 | Proxy IIS | Configuración de red y seguridad para la salida web. |
| | T-6.4 | Capacitación SOC | Entrega del sistema y entrenamiento a los analistas de seguridad. |

### 5.2. Fases de Implementación

El proyecto se planifica para una duración de **6 meses** (Septiembre 2026 - Febrero 2027), divididas en **6 Fases secuenciales**. Al finalizar cada fase, se obtendrá un avance significativo hacia la salida a producción.

*   **Fase 1: Ingeniería y Arquitectura (Septiembre 2026)**
    *   *Objetivo:* Definir las bases lógicas, estructurales y arquitectónicas del proyecto Artemis.
*   **Fase 2: Entorno y Configuración (Octubre 2026)**
    *   *Objetivo:* Preparar la infraestructura de desarrollo, repositorios y la base del framework Django.
*   **Fase 3: Construcción del Backend (Noviembre 2026)**
    *   *Objetivo:* Desarrollar el motor lógico de ingesta masiva y la gestión transaccional de estados.
*   **Fase 4: Desarrollo de Frontend (Diciembre 2026)**
    *   *Objetivo:* Crear la interfaz gráfica (UI/UX) y las capacidades de descarga (Empaquetador ZIP).
*   **Fase 5: Pruebas y Calidad (Enero 2027)**
    *   *Objetivo:* Asegurar el rendimiento y documentar el uso de la plataforma.
*   **Fase 6: Pase a Producción (Febrero 2027)**
    *   *Objetivo:* Despliegue en IIS, exposición de listas hacia las herramientas perimetrales y capacitación final.

### 5.2.1. Cronograma Visual (Diagrama de Gantt)

```plantuml
@startgantt
language es
printscale weekly
Project starts 2026-09-01

<style>
ganttDiagram {
  task {
    BackGroundColor #00B0F0
    LineColor #2F5597
    FontColor black
  }
}
</style>

' Fase 1
[1.1 Reglas de Negocio] starts 2026-09-01
[1.1 Reglas de Negocio] ends 2026-09-14
[1.2 Modelado de BD] starts 2026-09-08
[1.2 Modelado de BD] ends 2026-09-21
[1.3 Diseño C4] starts 2026-09-22
[1.3 Diseño C4] ends 2026-09-30

' Fase 2
[2.1 Repositorios Git] starts 2026-10-01
[2.1 Repositorios Git] ends 2026-10-07
[2.1 Repositorios Git] color is #82cda2
[2.2 Conexión ODBC] starts 2026-10-08
[2.2 Conexión ODBC] ends 2026-10-14
[2.2 Conexión ODBC] color is #82cda2
[2.3 Configuración de Django] starts 2026-10-15
[2.3 Configuración de Django] ends 2026-10-31
[2.3 Configuración de Django] color is #82cda2

' Fase 3
[3.1 Motor Ingesta/Regex] starts 2026-11-01
[3.1 Motor Ingesta/Regex] ends 2026-11-14
[3.1 Motor Ingesta/Regex] color is #94e09f
[3.2 Fragmentación de algoritmo] starts 2026-11-15
[3.2 Fragmentación de algoritmo] ends 2026-11-21
[3.2 Fragmentación de algoritmo] color is #94e09f
[3.3 API de Estados] starts 2026-11-22
[3.3 API de Estados] ends 2026-11-30
[3.3 API de Estados] color is #94e09f

' Fase 4
[4.1 Diseño UI/UX] starts 2026-12-01
[4.1 Diseño UI/UX] ends 2026-12-14
[4.1 Diseño UI/UX] color is #f8d77d
[4.2 Analistas de panel] starts 2026-12-15
[4.2 Analistas de panel] ends 2026-12-21
[4.2 Analistas de panel] color is #f8d77d
[4.3 Empaquetador ZIP] starts 2026-12-22
[4.3 Empaquetador ZIP] ends 2026-12-31
[4.3 Empaquetador ZIP] color is #f8d77d

' Fase 5
[5.1 Pruebas Unitarias] starts 2027-01-01
[5.1 Pruebas Unitarias] ends 2027-01-14
[5.1 Pruebas Unitarias] color is #d0b0df
[5.2 Pruebas de Estrés] starts 2027-01-15
[5.2 Pruebas de Estrés] ends 2027-01-21
[5.2 Pruebas de Estrés] color is #d0b0df
[5.3 Aceptación (UAT)] starts 2027-01-22
[5.3 Aceptación (UAT)] ends 2027-01-31
[5.3 Aceptación (UAT)] color is #d0b0df
[5.4 Desarrollo documentación] starts 2027-01-22
[5.4 Desarrollo documentación] ends 2027-01-31
[5.4 Desarrollo documentación] color is #d0b0df

' Fase 6
[6.1 Despliegue] starts 2027-02-01
[6.1 Despliegue] ends 2027-02-14
[6.1 Despliegue] color is #9cd3c1
[6.2 Publicacion de listas] starts 2027-02-01
[6.2 Publicacion de listas] ends 2027-02-14
[6.2 Publicacion de listas] color is #9cd3c1
[6.3 Proxy IIS] starts 2027-02-15
[6.3 Proxy IIS] ends 2027-02-21
[6.3 Proxy IIS] color is #9cd3c1
[6.4 Capacitación SOC] starts 2027-02-22
[6.4 Capacitación SOC] ends 2027-02-28
[6.4 Capacitación SOC] color is #9cd3c1
@endgantt
```

### 5.3. Plan de Despliegue con enfoque CI/CD

Dado el contexto restrictivo de la organización (uso exclusivo de Windows Server on-premise), se define una estrategia de Integración y Entrega Continua (CI/CD) adaptada a estos requerimientos:

1.  **Integración Continua (CI):** 
    *   El código fuente será gestionado en un repositorio centralizado (ej. GitHub/GitLab).
    *   Cada vez que un desarrollador realice un *Push* o apruebe un *Pull Request*, un *pipeline* automatizado ejecutará el *Linter* de Python, las Pruebas Unitarias (enfocadas fuertemente en el motor de validación Regex), y un escaneo de seguridad estática (SAST).
2.  **Entrega Continua (CD):** 
    *   Si las validaciones de CI son exitosas, un agente de despliegue (Runner) instalado localmente en el servidor Windows descargará el artefacto validado.
    *   El Runner ejecutará *scripts* de PowerShell para actualizar las dependencias de Python y reiniciar automáticamente el servicio *Waitress* (servidor de aplicaciones) que corre detrás del servidor web *Microsoft IIS*, logrando actualizaciones sin intervención manual prolongada.

### 5.4. Costos del Proyecto

La estimación de costos del proyecto abarca el desarrollo, la infraestructura y el licenciamiento necesario para el periodo de construcción e implementación (12 semanas / 6 Sprints).

| Categoría | Concepto | Costo Unitario (USD) | Cantidad | Costo Total Estimado (USD) |
| :--- | :--- | :--- | :---: | :---: |
| **Personal (Labor)** | Desarrollador Principal / Arquitecto | $650/mes | 3 meses | $1,950 |
| | Analista de Seguridad SOC (Apoyo validación) | $4.06/hora | 60 horas | $244 |
| **Infraestructura** | Servidor Windows Server On-Premise | $0 (Activo existente) | 1 | $0 |
| | Base de Datos MS SQL Server | $0 (Licencia corporativa) | 1 | $0 |
| **Software y Herramientas** | Python, Django, Waitress | Open Source | N/A | $0 |
| | Herramientas de CI/CD (GitHub Free) | $0 | 1 | $0 |
| **Contingencia** | Margen de imprevistos (10%) | - | - | $219 |
| **Total Estimado** | | | | **$2,413** |

> *Nota:* Al apalancarse en la infraestructura preexistente de la entidad financiera (Servidores Windows y licencias de base de datos) y en frameworks Open Source (Python/Django), los costos directos de software y hardware son nulos, recayendo el 100% de la inversión en las horas de ingeniería y desarrollo especializado.
