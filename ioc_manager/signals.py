from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    IocEntry,
    IocType,
    Tool,
    ToolIndicatorRule,
    IocTool
)


def detectar_tipo_ioc(valor):
    """ Detecta el tipo de IoC automáticamente. """
    valor = valor.strip()

    # HASH (SHA256 = 64 hex chars)
    import re
    if re.fullmatch(r"[A-Fa-f0-9]{64}", valor):
        return "Hash"

    # Dirección IP
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", valor):
        return "IP"

    # Correo
    if "@" in valor and "." in valor:
        return "Correo"

    # URL (contiene / o http)
    if valor.startswith("http://") or valor.startswith("https://") or "/" in valor:
        return "URL"

    # Dominio (texto + punto + tld)
    if re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,10}", valor):
        return "Dominio"

    return None


@receiver(post_save, sender=IocEntry)
def crear_relaciones_automatically(sender, instance, created, **kwargs):
    """
    Cada vez que se crea un IoC nuevo:
    - Detecta tipo si no está asignado
    - Busca reglas ToolIndicatorRule
    - Crea filas en IocTool automáticamente
    """

    if not created:
        return  # solo correr en creación

    ioc = instance

    # 1. Determinar tipo de IoC si no tiene
    if not ioc.ioc_type:
        tipo_detectado = detectar_tipo_ioc(ioc.value)

        if tipo_detectado:
            try:
                tipo = IocType.objects.get(name__iexact=tipo_detectado)
                ioc.ioc_type = tipo
                ioc.save(update_fields=["ioc_type"])
            except IocType.DoesNotExist:
                print(f"[WARN] Tipo detectado '{tipo_detectado}', pero no existe en DB.")
        else:
            print(f"[WARN] No se pudo detectar tipo de IoC: {ioc.value}")
            return

    # 2. Obtener herramientas que SI pueden procesar este tipo
    reglas = ToolIndicatorRule.objects.filter(
        ioc_type=ioc.ioc_type,
        can_ingest=True
    ).select_related("tool")

    if not reglas.exists():
        print(f"[INFO] No hay reglas para tipo {ioc.ioc_type.name}")
        return

    # 3. Crear IocTool automáticamente
    for regla in reglas:
        try:
            IocTool.objects.get_or_create(
                ioc=ioc,
                tool=regla.tool,
                defaults={"status": "pending", "created_at": timezone.now()}
            )
        except Exception as e:
            print(
                f"[ERROR] No se pudo crear relación IocTool "
                f"IoC={ioc.id} Tool={regla.tool.name}: {e}"
            )