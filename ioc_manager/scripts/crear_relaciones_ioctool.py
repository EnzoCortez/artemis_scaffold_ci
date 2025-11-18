# ioc_manager/scripts/crear_relaciones_ioctool.py
"""
Script idempotente para poblar ioc_manager_ioctool (IocTool)
a partir de las reglas existentes (ToolIndicatorRule, ToolHashType, FirewallIocType).
Uso (desde manage.py shell):
    from ioc_manager.scripts.crear_relaciones_ioctool import generar_relaciones_ioctool
    generar_relaciones_ioctool(dry_run=True, verbose=True)   # ensayo
    generar_relaciones_ioctool(dry_run=False, verbose=True)  # aplicar
"""

from typing import Dict, Any, List, Tuple, Set
from django.db import transaction
from django.db.utils import IntegrityError

from ioc_manager.models import (
    IocEntry,
    IocTool,
    Tool,
    ToolIndicatorRule,
    ToolHashType,
    FirewallIocType,
)

def generar_relaciones_ioctool(dry_run: bool = True, verbose: bool = True, limit: int = None, batch_size: int = 1000) -> Dict[str, Any]:
    """
    - dry_run: si True no escribe, solo imprime acciones.
    - verbose: si True imprime progreso.
    - limit: limita número de IoCs procesados (útil en pruebas).
    - batch_size: chunk size para iterator()
    Retorna dict con resumen.
    """
    created = 0
    skipped = 0
    errors: List[Tuple[int, str, str]] = []

    qs = IocEntry.objects.select_related('ioc_type').order_by('id')
    if limit:
        qs = qs[:limit]

    # iterar con iterator() para memoria
    for ioc in qs.iterator(chunk_size=batch_size):
        if verbose:
            print(f"[INFO] Procesando IOC {ioc.id} - tipo: {getattr(ioc.ioc_type, 'name', None)}")

        tools_set: Set[Tool] = set()

        # 1) Reglas explícitas: ToolIndicatorRule (herramienta <-> ioc_type)
        try:
            rules_qs = ToolIndicatorRule.objects.filter(ioc_type=ioc.ioc_type, can_ingest=True).select_related('tool')
            for r in rules_qs:
                if r.tool:
                    tools_set.add(r.tool)
        except Exception as e:
            if verbose:
                print(f"[WARN] fallo leyendo ToolIndicatorRule para IOC {ioc.id}: {e}")

        # 2) Reglas de hash por herramienta (ToolHashType)
        try:
            hash_qs = ToolHashType.objects.filter(ioc_type=ioc.ioc_type).select_related('tool')
            for h in hash_qs:
                if h.tool:
                    tools_set.add(h.tool)
        except Exception as e:
            if verbose:
                print(f"[WARN] fallo leyendo ToolHashType para IOC {ioc.id}: {e}")

        # 3) Firewalls (si existe mapping en FirewallIocType)
        try:
            fw_map_qs = FirewallIocType.objects.filter(ioc_type=ioc.ioc_type).select_related('firewall')
            if fw_map_qs.exists():
                # normalmente la herramienta que representa "firewall" tiene 'firewall' o 'waf' en su name
                fw_tools = list(Tool.objects.filter(name__icontains='firewall'))
                if not fw_tools:
                    fw_tools = list(Tool.objects.filter(name__icontains='waf'))
                for t in fw_tools:
                    tools_set.add(t)
        except Exception as e:
            if verbose:
                print(f"[WARN] fallo leyendo FirewallIocType para IOC {ioc.id}: {e}")

        # Si no hay herramientas detectadas — saltamos (se puede revisar después)
        if not tools_set:
            skipped += 1
            if verbose:
                print(f"[SKIP] IOC {ioc.id} ({ioc.value[:80]!r}) -> sin tools detectadas")
            continue

        # Asociar cada tool con get_or_create (idempotente)
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
                            print(f"[EXISTS] IOC {ioc.id} -> {tool.name} (ya existía)")
            except IntegrityError as ie:
                errors.append((ioc.id, tool.name, str(ie)))
                if verbose:
                    print(f"[ERROR] IntegrityError creando IocTool {ioc.id} -> {tool.name}: {ie}")
            except Exception as e:
                errors.append((ioc.id, tool.name, str(e)))
                if verbose:
                    print(f"[ERROR] Error creando IocTool {ioc.id} -> {tool.name}: {e}")

    # Resumen
    if verbose:
        print(f"Relaciones creadas: {created}")
        print(f"IOC sin tools asignadas: {skipped}")
        if errors:
            print("Errores (muestra hasta 20):")
            for e in errors[:20]:
                print(" ", e)

    return {"created": created, "skipped": skipped, "errors": errors}