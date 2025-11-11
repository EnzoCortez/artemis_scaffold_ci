# ioc_manager/scripts/crear_relaciones_ioctool.py
from django.db import IntegrityError, transaction
from ioc_manager.models import (
    IocEntry, IocTool, Tool, ToolHashType,
    ToolIndicatorRule, FirewallIocType
)

def generar_relaciones_ioctool(dry_run=False):
    """
    Genera relaciones IocTool usando las reglas disponibles:
      - ToolIndicatorRule (herramienta <-> tipo IOC, can_ingest=True)
      - ToolHashType (herramientas que soportan hashes para un tipo)
      - FirewallIocType -> si existe, se asocia a la herramienta cuyo name contiene 'Firewall'
    Parámetro:
      - dry_run: si True no guarda cambios, solo muestra lo que haría.
    """
    created = 0
    skipped = 0

    # Preload tools para búsquedas por nombre (evita consultas repetidas)
    tools_by_name = {t.name.strip().upper(): t for t in Tool.objects.all()}

    def find_firewall_tool():
        # intentamos encontrar un Tool con nombre parecido a 'Firewall'
        for key, t in tools_by_name.items():
            if 'FIREWALL' in key:
                return t
        # fallback: buscar en DB
        return Tool.objects.filter(name__icontains='firewall').first()

    firewall_tool = find_firewall_tool()

    iocs_qs = IocEntry.objects.select_related('ioc_type').all()

    for ioc in iocs_qs:
        tools_set = set()

        # 1) Reglas explícitas tool <-> ioc_type
        try:
            rules = ToolIndicatorRule.objects.filter(ioc_type=ioc.ioc_type, can_ingest=True).select_related('tool')
            for r in rules:
                if getattr(r, 'tool', None):
                    tools_set.add(r.tool)
        except Exception:
            # si el modelo no existe o hay problema, lo ignoramos (no fatal)
            pass

        # 2) ToolHashType (herramientas que aceptan este ioc_type para hashes)
        try:
            hash_types = ToolHashType.objects.filter(ioc_type=ioc.ioc_type).select_related('tool')
            for h in hash_types:
                if getattr(h, 'tool', None):
                    tools_set.add(h.tool)
        except Exception:
            pass

        # 3) Firewall mapping: si existe un FirewallIocType para este tipo, asociar tool 'Firewall' si existe
        try:
            if FirewallIocType.objects.filter(ioc_type=ioc.ioc_type).exists():
                if firewall_tool:
                    tools_set.add(firewall_tool)
        except Exception:
            pass

        if not tools_set:
            skipped += 1
            continue

        for tool in tools_set:
            try:
                if dry_run:
                    # sólo mostraría lo que haría
                    print(f"[DRY RUN] Asociar IOC {ioc.id} -> {tool.name}")
                    created += 1
                else:
                    with transaction.atomic():
                        obj, was_created = IocTool.objects.get_or_create(ioc=ioc, tool=tool)
                    if was_created:
                        created += 1
            except IntegrityError:
                # ya existe o violación de unicidad; safe ignore
                pass
            except Exception as e:
                print(f"Error creando relación IOC {ioc.id} -> {getattr(tool,'name',tool)}: {e}")

    # contar iocs sin tools asignadas (relación IocTool)
    iocs_sin_tool = IocEntry.objects.filter(tools__isnull=True).count()

    print(f"Relaciones creadas: {created}")
    print(f"IOC sin tools asignadas: {iocs_sin_tool} (saltados: {skipped})")
