# ioc_manager/utils.py
from django.utils import timezone
from .models import IocEntry, IocType, Tool, Ingestion

def create_or_get_ioc(ioc_type_name, value, created_by=None, source=None, upload_batch=None):
    """
    Crea o devuelve un IocEntry. Retorna (ioc, created_bool)
    """
    ioc_type, _ = IocType.objects.get_or_create(name=ioc_type_name)
    ioc, created = IocEntry.objects.get_or_create(
        ioc_type=ioc_type,
        value=value,
        defaults={
            'created_by': created_by,
            'source': source,
            'upload_batch': upload_batch,
            'status': IocEntry.STATUS_BLOCKED,
            'created_at': timezone.now()
        }
    )
    return ioc, created

def ingest_ioc_to_tool(ioc, tool_name, status=Ingestion.STATUS_INGESTED, detail=None, user=None):
    tool = Tool.objects.get(name=tool_name)
    ingestion = ioc.register_ingestion(tool=tool, status=status, ingested_at=timezone.now(), extra_comment=detail, user=user)
    return ingestion

def generar_txt_ingestions(qs=None):
    qs = qs or Ingestion.objects.select_related('ioc__ioc_type', 'tool').order_by('-created_at')[:1000]
    lines = []
    header = "id_ingestion\tid_ioc\tioc_value\tioc_type\ttool\tstatus\tingested_at\tcreated_at\tdetail"
    lines.append(header)
    for ing in qs:
        lines.append(
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                ing.pk,
                ing.ioc.pk,
                ing.ioc.value,
                ing.ioc.ioc_type.name if ing.ioc.ioc_type else "",
                ing.tool.name,
                ing.status,
                ing.ingested_at.isoformat() if ing.ingested_at else "",
                ing.created_at.isoformat() if ing.created_at else "",
                (ing.detail or "").replace("\n", " ")
            )
        )
    contenido = "\n".join(lines)
    filename = f"ingestions_{timezone.now().strftime('%Y%m%d%H%M%S')}.txt"
    return filename, contenido
