from django.utils import timezone
from ioc_manager.models import (
    IocEntry, IocTool, Ingestion,
    ToolIndicatorRule, IocHistory
)

def bulk_register_ingestion(iocs, user=None):
    """
    iocs: QuerySet o lista de IocEntry ya guardados
    """

    # 🔹 Precargar reglas tool <-> ioc_type
    rules = ToolIndicatorRule.objects.filter(can_ingest=True)
    rules_map = {}
    for r in rules:
        rules_map.setdefault(r.ioc_type_id, []).append(r.tool_id)

    ioc_tools_bulk = []
    ingestions_bulk = []
    history_bulk = []

    now = timezone.now()
    username = user.username if user and hasattr(user, 'username') else 'system'

    for ioc in iocs:
        tool_ids = rules_map.get(ioc.ioc_type_id, [])

        for tool_id in tool_ids:
            ioc_tools_bulk.append(
                IocTool(ioc_id=ioc.id, tool_id=tool_id)
            )
            ingestions_bulk.append(
                Ingestion(
                    ioc_id=ioc.id,
                    tool_id=tool_id,
                    status=Ingestion.STATUS_PENDING,
                    ingested_at=now
                )
            )
            history_bulk.append(
                IocHistory(
                    ioc=ioc,
                    action="IOC asociado automáticamente a herramienta",
                    user=username,
                    comment="Carga masiva optimizada"
                )
            )

    # 🔹 Deduplicación Python-side para MSSQL
    existing_q = IocTool.objects.filter(ioc__in=iocs).values_list('ioc_id', 'tool_id')
    existing_set = set(existing_q)

    final_ioc_tools = []
    for it in ioc_tools_bulk:
        if (it.ioc_id, it.tool_id) not in existing_set:
            final_ioc_tools.append(it)
            existing_set.add((it.ioc_id, it.tool_id))

    # 🔥 Inserts en bloque
    IocTool.objects.bulk_create(
        final_ioc_tools,
        batch_size=1000
    )
    Ingestion.objects.bulk_create(
        ingestions_bulk,
        batch_size=1000
    )
    IocHistory.objects.bulk_create(
        history_bulk,
        batch_size=1000
    )

from ioc_manager.models import IocEntry, IocLoadBatch, IocLoadResult
from ioc_manager.utils import detect_ioc_type

def validate_and_ingest(items, fuente):
    batch = IocLoadBatch.objects.create(
        source=fuente,
        total=len(items)
    )

    for value in items:
        value = value.strip()
        if not value:
            continue

        ioc_type = detect_ioc_type(value)

        if IocEntry.objects.filter(value=value).exists():
            IocLoadResult.objects.create(
                batch=batch,
                value=value,
                ioc_type=ioc_type,
                status='DUPLICADO'
            )
            batch.duplicated += 1
        else:
            IocEntry.objects.create(
                value=value,
                ioc_type=ioc_type,
                source=fuente
            )
            IocLoadResult.objects.create(
                batch=batch,
                value=value,
                ioc_type=ioc_type,
                status='INGESTADO'
            )
            batch.inserted += 1

    batch.save()
    return batch
