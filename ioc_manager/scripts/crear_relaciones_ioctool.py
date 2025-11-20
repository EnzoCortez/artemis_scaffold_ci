# ioc_manager/scripts/crear_relaciones_ioctool.py
from typing import Dict, Any, List, Tuple
from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import Q

from ioc_manager.models import (
    IocEntry, IocTool, Tool, ToolIndicatorRule, ToolHashType, FirewallIocType
)

def generar_relaciones_ioctool(dry_run: bool = True, verbose: bool = True, limit: int = None, batch_size: int = 1000) -> Dict[str, Any]:
    created = 0
    skipped = 0
    errors: List[Tuple[int, str, str]] = []

    qs = IocEntry.objects.select_related('ioc_type').order_by('id')
    if limit:
        qs = qs[:limit]

    for ioc in qs.iterator(chunk_size=batch_size):
        tools_set = set()

        # 1) Reglas explícitas (ToolIndicatorRule)
        try:
            rules_qs = ToolIndicatorRule.objects.filter(ioc_type=ioc.ioc_type, can_ingest=True).select_related('tool')
            for r in rules_qs:
                if r.tool:
                    tools_set.add(r.tool)
        except Exception as e:
            if verbose:
                print(f"[WARN] ToolIndicatorRule error IOC {ioc.id}: {e}")

        # 2) Hash rules (ToolHashType)
        try:
            hash_qs = ToolHashType.objects.filter(ioc_type=ioc.ioc_type).select_related('tool')
            for h in hash_qs:
                if h.tool:
                    tools_set.add(h.tool)
        except Exception as e:
            if verbose:
                print(f"[WARN] ToolHashType error IOC {ioc.id}: {e}")

        # 3) Firewall mapping: si existe mapping a FirewallIocType, mapear a Tools tipo Firewall
        try:
            fw_map_qs = FirewallIocType.objects.filter(ioc_type=ioc.ioc_type)
            if fw_map_qs.exists():
                fw_tools = list(Tool.objects.filter(name__icontains='firewall') | Tool.objects.filter(name__icontains='waf'))
                for t in fw_tools:
                    tools_set.add(t)
        except Exception as e:
            if verbose:
                print(f"[WARN] FirewallIocType error IOC {ioc.id}: {e}")

        if not tools_set:
            skipped += 1
            if verbose:
                print(f"[SKIP] IOC {ioc.id} ({ioc.value[:60]}) -> sin herramientas detectadas")
            continue

        for tool in tools_set:
            if dry_run:
                if verbose:
                    print(f"[DRY RUN] Asociar IOC {ioc.id} -> {tool.name}")
                continue
            try:
                with transaction.atomic():
                    obj, was_created = IocTool.objects.get_or_create(ioc=ioc, tool=tool)
                    if was_created:
                        created += 1
                        if verbose:
                            print(f"[CREATE] IOC {ioc.id} -> {tool.name}")
                    else:
                        if verbose:
                            print(f"[EXISTS] IOC {ioc.id} -> {tool.name}")
            except IntegrityError as ie:
                errors.append((ioc.id, tool.name, str(ie)))
                if verbose:
                    print(f"[ERROR] IntegrityError IocTool {ioc.id} -> {tool.name}: {ie}")
            except Exception as e:
                errors.append((ioc.id, tool.name, str(e)))
                if verbose:
                    print(f"[ERROR] Error IocTool {ioc.id} -> {tool.name}: {e}")

    if verbose:
        print(f"Relaciones creadas: {created}")
        print(f"IOC sin tools asignadas: {skipped}")
        if errors:
            print("Errores (muestra hasta 20):")
            for e in errors[:20]:
                print(" ", e)

    return {"created": created, "skipped": skipped, "errors": errors}
