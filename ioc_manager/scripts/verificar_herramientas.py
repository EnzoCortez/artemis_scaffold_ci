from django.db.models import Count
from ioc_manager.models import IocTool, Tool

def run():
    """
    Script de verificación y corrección de herramientas en Artemis.
    Ejecutar con:
        python manage.py runscript verificar_herramientas
    """

    print("=== VERIFICACIÓN Y CORRECCIÓN DE HERRAMIENTAS ===")

    # Lista esperada de herramientas
    herramientas_esperadas = ["EDR", "PROXY", "PROOFPOINT", "IPS", "FTD", "MERAKI", "FIREWALL"]

    # Correcciones automáticas de nombres
    correcciones = {
        "MERAKY": "MERAKI",
        "WAF": "FIREWALL"
    }

    # Aplicar correcciones en la tabla Tool
    for incorrecto, correcto in correcciones.items():
        count = Tool.objects.filter(name=incorrecto).update(name=correcto)
        if count > 0:
            print(f"✔ Renombrado '{incorrecto}' → '{correcto}' ({count} registro/s corregido/s)")

    # Mostrar herramientas existentes
    herramientas_en_bd = list(Tool.objects.values_list("name", flat=True))
    print("\n=== Verificación de herramientas registradas ===")
    for h in herramientas_esperadas:
        if h in herramientas_en_bd:
            print(f"✔ {h} está registrada en Tool")
        else:
            print(f"✖ {h} NO está registrada en Tool")

    # Conteo de IoCs asociados por herramienta
    print("\n=== Conteo de IoC asociados por herramienta ===")
    conteo_por_herramienta = (
        IocTool.objects
        .values("tool__name")
        .annotate(total_iocs=Count("ioc_entry", distinct=True))
        .order_by("tool__name")
    )

    if not conteo_por_herramienta:
        print("⚠ No existen relaciones entre IoC y Tool (tabla ioc_manager_ioctool está vacía).")
    else:
        for item in conteo_por_herramienta:
            print(f"{item['tool__name']:<15} → {item['total_iocs']} IoC asociados")

    # IoC presentes en todas las herramientas
    total_herramientas = len(herramientas_esperadas)
    iocs_en_todas = (
        IocTool.objects
        .values("ioc_entry")
        .annotate(total_tools=Count("tool", distinct=True))
        .filter(total_tools__gte=total_herramientas)
    )
    print(f"\n=== IoC compartidos entre todas las herramientas ===")
    print(f"Total de IoC presentes en TODAS las herramientas ({total_herramientas}): {iocs_en_todas.count()}")

    print("\n✅ Verificación completada.")
