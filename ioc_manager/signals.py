from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import IocEntry, IocTool, Tool, IocType

"""
IOC_TOOLS_MATRIX = {
    "Hash": ["EDR (Crowdstrike)", "IPS"],
    "Dominio": ["PROXY","EDR (Crowdstrike)","PROOFPOINT" ],
    "URL": ["PROXY"],
    "Correo": ["PROOFPOINT"],
    "IP": ["EDR (Crowdstrike)", "PROXY", "PROOFPOINT", "IPS", "FTD", "MERAKI"],
}


@receiver(post_save, sender=IocEntry)
def auto_associate_ioc_tools(sender, instance, created, **kwargs):
    if not created:
        return

    ioc_type_name = instance.ioc_type.name
    value = instance.value

    # Verificar tipo válido
    if ioc_type_name not in IOC_TOOLS_MATRIX:
        return

    tool_names = IOC_TOOLS_MATRIX[ioc_type_name]

    for tool_name in tool_names:
        try:
            tool = Tool.objects.get(name=tool_name)
            IocTool.objects.get_or_create(ioc=instance, tool=tool)
        except Tool.DoesNotExist:
            import logging
            logging.getLogger(__name__).warning(
                f"Tool '{tool_name}' no existe en BD, no se pudo asociar al IoC {instance.id}"
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"Error creando IocTool para IoC={instance.id} Tool={tool_name}: {e}"
            )
"""