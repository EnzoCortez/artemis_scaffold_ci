# Estimación de Costos del Proyecto Artemis

El presente análisis proyecta los costos asociados al desarrollo e implementación de la Plataforma Artemis, asumiendo un ciclo de vida de desarrollo de 4 meses (16 semanas) conforme a la Estructura de Desglose de Trabajo (EDT). 

Para esta estimación, se ha utilizado un enfoque *Bottom-Up* (de abajo hacia arriba), calculando los costos de recursos humanos (basados en tarifas estándar de mercado para perfiles Junior/Mid), licenciamiento de software, e infraestructura tecnológica.

---

## 1. Costos de Recursos Humanos (Labor Directa)

Al tratarse de un desarrollo de software *In-House*, el mayor peso económico recae sobre el equipo de ingeniería. Se estima una dedicación de medio tiempo (20 horas semanales) por desarrollador durante las 16 semanas del proyecto.

| Rol en el Proyecto | Tarifa por Hora (USD) | Horas Estimadas | Costo Total Estimado |
| :--- | :--- | :--- | :--- |
| **Ingeniero de Software / Arquitecto** (Desarrollo Django, SQL, Arquitectura C4) | $15.00 | 320 hrs | $4,800.00 |
| **Analista de Calidad (QA) / UI** (Pruebas unitarias, UAT, Diseño de Interfaz) | $12.00 | 160 hrs | $1,920.00 |
| **Subtotal Recursos Humanos** | | **480 hrs** | **$6,720.00** |

## 2. Costos de Software y Licenciamiento

Artemis ha sido diseñado estratégicamente para aprovechar tecnologías de código abierto (*Open Source*) y recursos corporativos preexistentes, reduciendo drásticamente la barrera de inversión inicial (CAPEX).

| Recurso / Tecnología | Tipo de Licencia | Costo Mensual | Costo Total (4 Meses) |
| :--- | :--- | :--- | :--- |
| **Python & Framework Django** | Open Source (Gratuito) | $0.00 | $0.00 |
| **Motor MS SQL Server** | Licencia Corporativa (Ya adquirida por la empresa) | $0.00* | $0.00* |
| **Servidor Python (Waitress)** | Open Source (Gratuito) | $0.00 | $0.00 |
| **IDE de Desarrollo** (VS Code) | Open Source (Gratuito) | $0.00 | $0.00 |
| **Subtotal Software** | | | **$0.00** |

*\*Nota: El uso de MS SQL Server e IIS no representa un costo para el proyecto ya que se despliega sobre la infraestructura heredada (*legacy*) que la institución ya posee y licencia anualmente.*

## 3. Costos de Infraestructura y Hardware

| Recurso | Descripción | Costo Unitario | Costo Total |
| :--- | :--- | :--- | :--- |
| **Estaciones de Trabajo (Laptops)** | Depreciación de equipos de cómputo para desarrollo (2 unidades). | $150.00 | $300.00 |
| **Servidor de Pruebas (VM)** | Uso de entorno de máquina virtual local para pruebas de integración. | $0.00* | $0.00 |
| **Servidor de Producción** | Aprovisionamiento en el Data Center local del cliente. | $0.00* | $0.00 |
| **Subtotal Infraestructura** | | | **$300.00** |

*\*Nota: Los servidores virtuales (VM) son aprovisionados por el hipervisor interno de la organización (Ej. VMware/Hyper-V), no requiriendo alquiler de nube pública (AWS/Azure).*

## 4. Costos Indirectos (Operativos)

Gastos derivados del entorno de trabajo durante el periodo de 4 meses.

| Concepto | Costo Mensual Estimado | Costo Total (4 Meses) |
| :--- | :--- | :--- |
| Servicios Básicos (Energía e Internet) | $40.00 | $160.00 |
| Imprevistos / Contingencia (10% del total base) | N/A | $718.00 |
| **Subtotal Costos Indirectos** | | **$878.00** |

---

## 5. Presupuesto Total Consolidado

La siguiente tabla resume la inversión total estimada para la construcción e implementación exitosa de la Plataforma Artemis desde cero:

| Categoría de Costo | Monto (USD) | Porcentaje del Presupuesto |
| :--- | :--- | :--- |
| Recursos Humanos (Ingeniería) | $6,720.00 | 85.1% |
| Licenciamiento de Software | $0.00 | 0.0% |
| Infraestructura y Hardware | $300.00 | 3.8% |
| Costos Indirectos y Contingencias | $878.00 | 11.1% |
| **GRAN TOTAL ESTIMADO** | **$7,898.00** | **100%** |

### **Análisis de Rentabilidad (Justificación):**
El costo total proyectado de **$7,898.00 USD** es sustancialmente inferior a la adquisición e integración de plataformas SOAR o administradores de amenazas comerciales de terceros (cuyas licencias anuales suelen superar los $25,000 USD). La decisión arquitectónica de basar Artemis en Python/Django (*Open Source*) elimina por completo el costo de licenciamiento de software. Al finalizar los 4 meses, la organización poseerá un activo tecnológico perpetuo y a medida, con un Retorno de Inversión (ROI) altísimo al eliminar las horas de trabajo manual del equipo SOC.
