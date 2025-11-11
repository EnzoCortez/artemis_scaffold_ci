from ioc_manager.models import IocEntry, IocTool, ToolHashType, Tool, FirewallIocType, Firewall
from django.db import IntegrityError

def asignar_tools():
    created = 0
    skipped = 0

    for ioc in IocEntry.objects.select_related('ioc_type').all():
        itype = getattr(ioc.ioc_type, 'id', None)
        if not itype:
            skipped += 1
            continue

        # 1) buscar ToolHashType: tools que aceptan este ioc_type
        tools_qs = Tool.objects.filter(hash_types__ioc_type=ioc.ioc_type).distinct()

        # 2) buscar FirewallIocType (si aplica)
        try:
            fw_tools_qs = Tool.objects.filter(name__iexact='Firewall') if Firewall.objects.exists() else Tool.objects.none()
        except Exception:
            fw_tools_qs = Tool.objects.none()

        tools = list(tools_qs) + list(fw_tools_qs)
        if not tools:
            skipped += 1
            continue

        for t in tools:
            try:
                IocTool.objects.create(ioc=ioc, tool=t)
                created += 1
            except IntegrityError:
                # ya existía
                pass
            except Exception as e:
                print("Error creando relación:", ioc.id, t.name, e)

    print(f"✅ Relaciones creadas: {created}")
    print(f"⏭️  IOC sin tools asignadas: {skipped}")
