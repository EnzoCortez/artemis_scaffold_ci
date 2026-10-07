## 6. Descripción de estudios realizados

### 6.1. Introducción al Estado del Arte en Inteligencia de Amenazas
En la actualidad, el incremento exponencial de ciberataques ha obligado a los Centros de Operaciones de Seguridad (SOC) a evolucionar sus mecanismos de defensa. La recolección manual de Indicadores de Compromiso (IoCs) a través de foros, correos electrónicos o repositorios no estructurados se ha vuelto obsoleta debido al volumen y la velocidad con la que mutan las amenazas. Esto ha dado lugar a la consolidación de las **Plataformas de Inteligencia de Amenazas (TIP - Threat Intelligence Platforms)** (Brown & Lee, 2023).

Las plataformas TIP modernas tienen como objetivo centralizar, normalizar, validar y distribuir inteligencia accionable hacia dispositivos perimetrales (Firewalls, IPS, EDR) casi en tiempo real. A nivel de industria, la adopción de estándares estructurados como STIX (Structured Threat Information Expression) y TAXII (Trusted Automated Exchange of Intelligence Information) ha estandarizado la forma en que las organizaciones comparten esta información (OASIS Open, 2021). Sin embargo, la adopción de plataformas TIP de grado empresarial conlleva desafíos arquitectónicos significativos.

### 6.2. Revisión de Plataformas Líderes en el Mercado

Para fundamentar la necesidad de la Plataforma Artemis, se ha realizado una investigación exhaustiva sobre las dos herramientas Open Source más dominantes y maduras del mercado global de ciberseguridad.

#### 6.2.1. MISP (Malware Information Sharing Platform)
MISP es indiscutiblemente el estándar de facto para el intercambio colaborativo de información sobre amenazas, utilizado extensivamente por CERTs, equipos militares y consorcios ISAC (Information Sharing and Analysis Centers) en todo el mundo.
*   **Enfoque:** Su arquitectura es "centrada en eventos". Un evento agrupa múltiples atributos (IoCs) que describen un ataque.
*   **Fortalezas:** Excelente capacidad para integrarse con cientos de fuentes y compartir datos criptográficamente firmados con otras instancias MISP (Wagner et al., 2022).
*   **Arquitectura Base:** Es una aplicación monolítica escrita principalmente en PHP, que depende fuertemente de un entorno LAMP (Linux, Apache, MySQL/MariaDB, PHP) y redis para cacheo.

#### 6.2.2. OpenCTI (Open Cyber Threat Intelligence)
Desarrollada inicialmente por la Agencia Nacional de Ciberseguridad de Francia (ANSSI), OpenCTI representa la nueva generación de TIPs centrada en la "analítica de grafos" y el modelado completo del comportamiento del adversario.
*   **Enfoque:** Modela la inteligencia como un grafo de conocimiento nativo en STIX 2.1, relacionando Actores de Amenazas, Campañas y TTPs (Tácticas, Técnicas y Procedimientos) (OpenCTI, 2024).
*   **Fortalezas:** Interfaz visual sumamente moderna orientada a la investigación profunda (Threat Hunting) y deducción algorítmica de amenazas.
*   **Arquitectura Base:** Es un ecosistema de microservicios altamente complejo que requiere la orquestación simultánea de Node.js, Python, Elasticsearch, Redis, RabbitMQ y MinIO, ejecutándose de manera casi obligatoria sobre Docker o Kubernetes.

### 6.3. Análisis de Limitaciones frente a Restricciones Corporativas

Si bien tanto MISP como OpenCTI son líderes indiscutibles desde el punto de vista analítico, la investigación documental revela que su adopción directa fracasa en organizaciones con madurez estricta en controles de infraestructura.

Para el presente proyecto, **ambas herramientas han sido declaradas técnica y normativamente inviables** debido a las siguientes restricciones críticas del entorno operativo:

1.  **Normativas de Seguridad Interna (Zero Linux Policy):** El banco (entorno objetivo del proyecto) posee normativas de seguridad de la información que prohíben la homologación y exposición de sistemas operativos basados en Linux dentro de los segmentos de red críticos (DMZ y redes de gestión SOC). Toda la infraestructura corporativa autorizada debe correr sobre ecosistemas Windows Server. Tanto MISP como OpenCTI no ofrecen soporte nativo ni instaladores oficiales para Windows Server.
2.  **Restricciones de Orquestación y Docker:** Intentar virtualizar estas herramientas (usando WSL2, Hyper-V o Docker Desktop para Windows) incurre en violaciones directas a las políticas de *hardening* perimetral. La inserción de tecnologías de contenedores (Docker) y colas de mensajería asíncronas de terceros (RabbitMQ) no aprobadas por el comité de arquitectura introduce una superficie de ataque y una sobrecarga operativa inaceptable.
3.  **Restricción de Motores de Base de Datos:** OpenCTI requiere Elasticsearch y MISP requiere MariaDB. Las políticas internas de la organización restringen la instalación de bases de datos no estandarizadas, permitiendo únicamente el uso de la granja corporativa existente basada en Microsoft SQL Server.

En resumen, la fricción arquitectónica y el incumplimiento normativo hacen que el despliegue de herramientas globales sea imposible sin alterar drásticamente la política de infraestructura de la empresa.

### 6.4. Comparativa de Mercado y Justificación de Artemis

Frente a la inviabilidad de implementar herramientas monolíticas basadas en Linux o ecosistemas de microservicios masivos, surge la justificación técnica para el desarrollo de **Artemis**. 

Artemis no busca competir con las capacidades de modelado de grafos de OpenCTI ni con la red de sindicación global de MISP; su propósito es actuar como un **Middleware Táctico y Ligero**, resolviendo el dolor operativo exacto del Analista SOC bajo el estricto cumplimiento de las normativas vigentes.

| Criterio Técnico | MISP | OpenCTI | Plataforma Artemis (Propuesta) |
| :--- | :--- | :--- | :--- |
| **Soporte de Sistema Operativo** | Linux Ubuntu/CentOS (Nativo) | Linux / Contenedores (Nativo) | **Windows Server (Nativo / IIS)** |
| **Motor de Base de Datos** | MySQL / MariaDB | Elasticsearch / Redis / MinIO | **MS SQL Server (Soportado nativamente)** |
| **Arquitectura requerida** | LAMP Stack Monolítico | Microservicios (Docker/K8s) | **Monolito Ligero (Python/Django)** |
| **Cumplimiento Normativo Interno** | ❌ Inviable (Requiere Linux) | ❌ Inviable (Requiere Docker) | ✅ **100% Viable (On-Premise estándar)** |
| **Enfoque Principal** | Sindicación global de IoCs. | Threat Hunting y Grafos de STIX. | **Validación transaccional táctica (Regex) y ruteo.** |
| **Sobrecarga de Hardware** | Moderada a Alta | Muy Alta (Min. 16GB RAM) | **Muy Baja (< 2GB RAM)** |

**Justificación Final:** Artemis es una opción superior y necesaria porque adapta el concepto moderno de una TIP a un entorno *legacy* altamente restrictivo. Permite a los analistas abandonar la manipulación manual de archivos `.txt`, implementando validación criptográfica y limpieza masiva de datos (deduplicación), para luego exponer los IoCs de forma segura a los Firewalls. Todo esto sin introducir nuevas tecnologías ajenas a la pila de Microsoft (IIS/SQL Server), garantizando un despliegue sin fricciones y con total aprobación de los comités de seguridad interna.

### 6.5. Selección de la Mejor Solución (Matriz de Decisión)

La selección de la mejor alternativa se sustenta técnicamente utilizando la norma **ISO 25010:2023** como marco de referencia para los atributos de calidad del software. Se comparan objetivamente dos alternativas arquitectónicas viables:

*   **Alternativa 1 (A1):** Arquitectura Monolítica con Django (Python) sobre Windows Server / IIS / SQL Server.
*   **Alternativa 2 (A2):** Arquitectura de Microservicios (Node.js + Python) con contenedores Docker y bases NoSQL.

Los criterios de evaluación se derivan directamente de los requisitos no funcionales y las restricciones operativas del entorno bancario. Se emplea una escala de valoración de **1 a 5** (donde 5 = Excelente, 1 = Deficiente) aplicable a todos los criterios. Los pesos asignados reflejan la prioridad del entorno operativo.

#### Matriz de Decisión:

**Tabla 1**

*Matriz de decisión ponderada para la selección de la alternativa arquitectónica del proyecto Artemis*

| Criterio | Alternativa 1 (Monolítica Django) | Justificación 1 | Alternativa 2 (Microservicios) | Justificación 2 |
| :--- | :---: | :--- | :---: | :--- |
| Portabilidad / Compatibilidad con Windows Server (30%) | 5 | Django se despliega nativamente sobre Windows Server mediante Waitress + IIS como proxy inverso, cumpliendo al 100% la política *Zero Linux* (ISO 25010: Portabilidad). | 1 | Requiere Docker, Kubernetes y componentes nativos de Linux. Su despliegue en Windows Server es experimental y viola las políticas de *hardening* perimetral de la organización. |
| Eficiencia de desempeño (20%) | 4 | Alto rendimiento mediante técnicas de *Chunking* (fragmentación ACID) y procesamiento síncrono optimizado; latencia controlada para volúmenes de hasta 150k registros (ISO 25010: Eficiencia de desempeño). | 5 | Arquitectura inherentemente asíncrona con escalamiento horizontal nativo; superior en escenarios de altísima concurrencia distribuida. |
| Mantenibilidad / Soporte (25%) | 5 | Código centralizado en un solo repositorio bajo el patrón MVT de Django. Un único desarrollador puede mantener y depurar toda la plataforma sin orquestación externa (ISO 25010: Mantenibilidad). | 2 | Alto acoplamiento entre microservicios genera complejidad operativa significativa; requiere equipo especializado en DevOps, monitoreo de colas (RabbitMQ) y múltiples repositorios. |
| Seguridad e integridad ACID (25%) | 5 | SQL Server ofrece transacciones ACID blindadas y auditoría nativa. Django ORM garantiza integridad referencial estricta sobre el motor corporativo aprobado (ISO 25010: Seguridad). | 3 | Las bases NoSQL (Elasticsearch, Redis) son eventualmente consistentes; no garantizan atomicidad transaccional nativa, lo cual es un riesgo para datos críticos de inteligencia. |
| **Total ponderado** | **4.80** | | **2.55** | |

*Nota.* La escala de valoración es de 1 a 5 (1 = Deficiente, 5 = Excelente). Los criterios y sus pesos se derivan de los requisitos no funcionales del entorno operativo y se evalúan conforme a los atributos de calidad definidos en la norma ISO/IEC 25010:2023 (ISO, 2023). Adaptado de *Systems and Software Engineering — Product Quality Model*, por ISO/IEC, 2023.

**Tabla 2**

*Desglose del cálculo del puntaje ponderado por criterio*

| Criterio | Peso | Puntuación A1 | Ponderado A1 | Puntuación A2 | Ponderado A2 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Portabilidad | 30% | 5 | 1.50 | 1 | 0.30 |
| Eficiencia de desempeño | 20% | 4 | 0.80 | 5 | 1.00 |
| Mantenibilidad / Soporte | 25% | 5 | 1.25 | 2 | 0.50 |
| Seguridad e integridad (ACID) | 25% | 5 | 1.25 | 3 | 0.75 |
| **Total** | **100%** | | **4.80** | | **2.55** |

*Nota.* Ponderado = Peso (%) × Puntuación. La suma de los pesos totaliza el 100%.

**Conclusión:** La **Alternativa 1 (Arquitectura Monolítica con Django)** obtiene una puntuación ponderada de **4.80/5.00**, superando ampliamente a la Alternativa 2 (2.55/5.00). La decisión se fundamenta en que los criterios de mayor peso — Portabilidad (30%) y Seguridad ACID (25%) — son requisitos innegociables impuestos por las políticas de infraestructura de la organización, donde la Alternativa 2 es directamente inviable. Aunque los microservicios ofrecen una ligera ventaja en eficiencia bajo concurrencia extrema, esta ganancia no compensa la imposibilidad de despliegue ni el costo de mantenimiento que introducen en este contexto corporativo (ISO, 2023).

### 6.6. Referencias Bibliográficas

*   Brown, A., & Lee, R. M. (2023). *The Evolution of Threat Intelligence Platforms in Modern Security Operations*. SANS Institute. Recuperado de la biblioteca digital del SANS.
*   MISP Project. (2024). *MISP - Open Source Threat Intelligence and Sharing Platform*. Recuperado de https://www.misp-project.org/
*   OASIS Open. (2021). *STIX Version 2.1. OASIS Standard*. Recuperado de https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html
*   OpenCTI. (2024). *Open Cyber Threat Intelligence Platform Documentation*. Filigran. Recuperado de https://docs.opencti.io/
*   Wagner, T., et al. (2022). *Cyber Threat Intelligence Sharing: A Comprehensive Review of the MISP Ecosystem*. Journal of Cybersecurity Research, 14(2), 112-130.
