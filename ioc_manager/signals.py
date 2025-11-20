from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import IocEntry
from .scripts.crear_relaciones_ioctool import generar_relaciones_ioctool

@receiver(post_save, sender=IocEntry)
def auto_associate_ioc_tools(sender, instance, created, **kwargs):
    """
    Al crear un nuevo IocEntry, ejecutar una asociación puntual usando
    la lógica del script (dry_run=False pero solo para ese IOC).
    """
    if not created:
        return
    # ejecutar solo para este IOC (limit=1 y dry_run False)
    # la función original trabaja por batch; aquí podemos invocar una versión
    # ligera: por simplicidad, llamar generar_relaciones_ioctool(limit=...) no funciona
    # mejor: reusar la lógica mínimamente para una sola entrada:
    from .models import ToolIndicatorRule, ToolHashType, FirewallIocType, IocTool, Tool
    tools_set = set()
    try:
        for r in ToolIndicatorRule.objects.filter(ioc_type=instance.ioc_type, can_ingest=True).select_related('tool'):
            tools_set.add(r.tool)
    except:
        pass
    try:
        for h in ToolHashType.objects.filter(ioc_type=instance.ioc_type).select_related('tool'):
            tools_set.add(h.tool)
    except:
        pass
    try:
        if FirewallIocType.objects.filter(ioc_type=instance.ioc_type).exists():
            fw_tools = list(Tool.objects.filter(name__icontains='firewall') | Tool.objects.filter(name__icontains='waf'))
            for t in fw_tools:
                tools_set.add(t)
    except:
        pass

    for tool in tools_set:
        try:
            IocTool.objects.get_or_create(ioc=instance, tool=tool)
        except Exception as e:
            # loggear pero no fallar
            import logging
            logging.getLogger(__name__).error(f"No se pudo crear relación IocTool IoC={instance.id} Tool={getattr(tool,'name',tool)}: {e}")
