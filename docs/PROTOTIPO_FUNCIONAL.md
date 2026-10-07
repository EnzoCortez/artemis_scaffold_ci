# 7. Prototipo Funcional de la Plataforma Artemis

Esta sección presenta las interfaces del prototipo funcional de Artemis, diseñado para cumplir con los requerimientos operativos de ingesta, gestión, reporte y distribución de Indicadores de Compromiso (IoCs). La interfaz mantiene un diseño unificado y coherente con el entorno corporativo y el esquema oscuro característico de las herramientas de ciberseguridad.

### 7.1. Módulo de Carga e Ingesta
Esta pantalla es el punto de entrada principal para el analista de seguridad. Permite seleccionar la fuente de inteligencia (ej. IBM, Cisco, Kaspersky) y cargar archivos de texto plano (.txt) con los indicadores de compromiso recopilados. Antes de la ingesta en la base de datos, el sistema aplica una validación criptográfica y reglas de limpieza, separando visualmente los datos en tres categorías:
*   **IoCs nuevos listos para ingestar:** Indicadores limpios y válidos que no existen en el sistema.
*   **Duplicados detectados:** Indicadores que ya han sido registrados previamente, optimizando el almacenamiento.
*   **Rechazados / No Válidos:** Entradas que no cumplen con los formatos estandarizados o se consideran inválidas.

![Carga IoC](file:///C:/Users/lenovo/Downloads/Nueva%20carpeta/Carga%20inicial.png)

---

### 7.2. Módulo de Depuración
Diseñado para la gestión ágil de los archivos resultantes de la carga, este módulo permite a los analistas descargar rápidamente los reportes de depuración. Facilita la generación y descarga de archivos de texto tanto de los indicadores duplicados como de los nuevos ingresados al sistema, manteniendo un registro auditable de cada lote procesado.

![Depuración](file:///C:/Users/lenovo/Downloads/Nueva%20carpeta/Depuraci%C3%B3n.png)

---

### 7.3. Gestión de Estados
Este panel proporciona visibilidad y control sobre el ciclo de vida completo de cada indicador en la base de datos.
*   **Tabla de IoCs:** Lista todos los indicadores detallando su valor, tipo (IP, Dominio, Hash, etc.) y estado actual (Bloqueado, Observación, etc.). Incluye botones para cambiar el estado de manera individual y ver los detalles.
*   **Filtros:** Permite la búsqueda rápida por valor y el filtrado por fechas.
*   **Carga masiva:** Ofrece la capacidad operativa de actualizar el estado de miles de indicadores simultáneamente cargando un archivo `.txt` y seleccionando el nuevo estado objetivo.

![Gestión de Estados](file:///C:/Users/lenovo/Downloads/Nueva%20carpeta/Gestion%20de%20estados.png)

---

### 7.4. Reportes
La interfaz de Reportes permite a los administradores generar informes consolidados de la actividad de los indicadores a través de parámetros como rango de fechas, fuente de origen y tipo de IoC. 
Además, incluye la funcionalidad avanzada de **Reporte de Análisis por TXT Subido**, que cruza la información de un archivo de prueba contra la base de datos para identificar al instante qué indicadores ya están ingestados y cuáles no, facilitando las tareas de *Threat Hunting*.

![Reportes](file:///C:/Users/lenovo/Downloads/Nueva%20carpeta/Reportes.png)

---

### 7.5. Mantenimiento y Dashboard Analítico
Esta vista técnica se enfoca en el estado general del sistema y el mantenimiento preventivo de la base de datos:
*   **Dashboard de Métricas:** Presenta visualmente la distribución actual de los indicadores almacenados en el sistema mediante gráficos interactivos (proporción de tipos de IoC en anillo y volumetría por estado en barras).
*   **Mantenimiento de Base de Datos (SQL Server):** Permite al administrador técnico auditar el peso del archivo de Log de Transacciones (LDF) y ejecutar rutinas de compactación (Shrink) para evitar la saturación del disco del servidor, respondiendo directamente a los requerimientos no funcionales de infraestructura.

![Mantenimiento](file:///C:/Users/lenovo/Downloads/Nueva%20carpeta/Mantenimiento.png)

---

### 7.6. Administración de Distribución de Indicadores (Módulo de Despliegue)
Este módulo gestiona la capa de salida táctica de Artemis. Actúa como el centro de control donde se configuran y monitorean las herramientas de seguridad perimetral (Firewalls, IPS, EDR, WAF) que consumirán los IoCs.
El panel expone el nombre de cada herramienta integrada, la URL del endpoint API dedicado para consumo, el estado de conectividad y la métrica en tiempo real de cuántos indicadores han sido distribuidos y sincronizados exitosamente, cerrando el ciclo de la inteligencia de amenazas.

![Administración de Distribución](file:///C:/Users/lenovo/Downloads/Nueva%20carpeta/Distribucion.png)

*(Nota: Capturar la imagen desde el archivo `docs/distribucion_mockup.html` y guardarla en la carpeta de descargas con el nombre `Distribucion.png` para que enlace automáticamente aquí).*
