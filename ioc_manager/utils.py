# ioc_manager/utils.py
import re
from typing import Optional, Tuple
from django.utils import timezone
from .models import IocEntry, IocType, Tool, IocTool

# ==========================================================
# 1. DETECTORES DE IOC (robustos)
# ==========================================================

_RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_RE_IPV4 = re.compile(r"^(25[0-5]|2[0-4]\d|1?\d{1,2})(\.(25[0-5]|2[0-4]\d|1?\d{1,2})){3}$")
_RE_IPV6 = re.compile(r"^([0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}$")

# Dominio válido (subdominios permitidos con guiones, underscores y unicode)
DOMAIN_REGEX = re.compile(
    r"^(?=.{1,253}$)(?:[\w-]{1,63}\.)+[A-Za-z]{2,63}$",
    re.UNICODE
)


# URL robusta: acepta con o sin protocolo, subdominios, puerto opcional y rutas
_RE_URL = re.compile(
    r"\b((?:https?://)?(?:[\w-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?)\b",
    re.UNICODE
)

# hex para hashes (longitudes 32/40/64/128)
_RE_HEX = re.compile(r"^[A-Fa-f0-9]{32,128}$")


def detect_hash_algorithm(value: str) -> Optional[str]:
    """Detecta MD5 / SHA1 / SHA256 / SHA512 por longitud hex."""
    if not value:
        return None
    v = value.strip()
    if not _RE_HEX.fullmatch(v):
        return None
    L = len(v)
    return {
        32: "md5",
        40: "sha1",
        64: "sha256",
        128: "sha512"
    }.get(L, None)

def remove_defanging(value: str) -> str:
    """Remueve ofuscaciones comunes de indicadores (ej. [.] -> . , (-) -> -)"""
    if not value:
        return value
    v = value.replace("[.]", ".").replace("(.)", ".").replace("{.}", ".")
    v = v.replace("[-]", "-").replace("(-)", "-").replace("{-}", "-")
    v = v.replace("[ : ]", ":").replace("[:]", ":")
    return v

def apply_defanging(value: str, ioc_type: str = None) -> str:
    """
    Aplica ofuscación (defanging) a un indicador para exportación segura.
    Los Hashes NO se ofuscan. Para IPs y dominios reemplaza '.' por '[.]'.
    Para URLs reemplaza 'http' por 'hxxp' y '.' por '[.]'.
    """
    if not value:
        return value

    # No ofuscar hashes
    if ioc_type and 'hash' in ioc_type.lower():
        return value
    # Doble verificación: si parece hash por longitud, no ofuscar
    if detect_hash_algorithm(value):
        return value

    v = value

    # URLs: reemplazar protocolo y puntos
    if v.lower().startswith("http://"):
        v = "hxxp://" + v[7:]
    elif v.lower().startswith("https://"):
        v = "hxxps://" + v[8:]

    # Reemplazar puntos por [.] (aplica a IPs, dominios y URLs)
    v = v.replace(".", "[.]")

    return v

def detect_ioc_type(value: str) -> Optional[str]:
    """
    Devuelve uno de los tipos conocidos:
    - "Hash", "IP", "Dominio", "URL", "Correo"
    Si no puede determinar, retorna None.
    """
    if not value:
        return None
    
    # 1. Limpiar ofuscación (XP: Defanging robusto)
    v = remove_defanging(value).strip()

    # Email
    if _RE_EMAIL.fullmatch(v):
        return "Correo"

    # IPv4 / IPv6
    if _RE_IPV4.fullmatch(v) or _RE_IPV6.fullmatch(v):
        return "IP"

    # Hash
    if detect_hash_algorithm(v):
        return "Hash"

    # URL explícita (con protocolo)
    if v.lower().startswith("http://") or v.lower().startswith("https://"):
        return "URL"

    # URL implícita: tiene "/" y la parte izquierda es dominio válido
    if "/" in v:
        parts = v.split("/", 1)
        left = parts[0]
        # Si tiene path y el host parece dominio, es URL
        if DOMAIN_REGEX.fullmatch(left):
             return "URL"


        # Dominio simple
    if DOMAIN_REGEX.fullmatch(v):
        return "Dominio"

    return None


# ==========================================================
# 2. VALIDACION DINAMICA DE HERRAMIENTAS
# ==========================================================

def validate_tool_accepts_ioc(tool_name: str, value: str) -> Tuple[bool, Optional[str]]:
    """
    Valida si una herramienta puede ingerir un IOC basándose en la base de datos.
    Retorna: (True, None) si se puede
            (False, "motivo") si NO se permite
    """
    tipo = detect_ioc_type(value)
    if not tipo:
        return False, f"No se reconoce el tipo de IOC para '{value}'."

    # Resolver herramienta (exact match case-insensitive, luego partial)
    tool = Tool.objects.filter(name__iexact=tool_name).first()
    if not tool:
         tool = Tool.objects.filter(name__icontains=tool_name).first()
         
    if not tool:
        return False, f"Herramienta '{tool_name}' no existe en base de datos."

    from .models import ToolIndicatorRule, ToolHashType

    # Chequear regla de ingesta dinámica
    rule = ToolIndicatorRule.objects.filter(tool=tool, ioc_type__name__iexact=tipo, can_ingest=True).exists()
    if not rule:
        return False, f"'{tool.name}' no tiene habilitada la ingesta de '{tipo}'."

    # si es Hash, validar algoritmo
    if tipo == "Hash":
        algo = detect_hash_algorithm(value)
        if not algo:
            return False, "Hash inválido."
            
        # Si la herramienta tiene mapeos de algoritmos, verificar. Si no tiene ninguno configurado, acepta todos.
        hash_configs = ToolHashType.objects.filter(tool=tool, ioc_type__name__iexact="Hash").values_list('algorithm', flat=True)
        if hash_configs:
            allowed_algos = [h.lower().strip() for h in hash_configs]
            if algo not in allowed_algos:
                return False, f"'{tool.name}' solo acepta hashes: {', '.join(allowed_algos)}."

    return True, None


# ==========================================================
# 3. UTILIDADES (create/ingest/generar_txt)
# ==========================================================

def create_or_get_ioc(ioc_type_name: str, value: str, created_by=None, source=None, upload_batch=None):
    """
    Crea o devuelve un IocEntry. Retorna (ioc, created_bool)
    """
    ioc_type, _ = IocType.objects.get_or_create(name=ioc_type_name)
    ioc, created = IocEntry.objects.get_or_create(
        ioc_type=ioc_type,
        value=value,
        defaults={
            "created_by": created_by,
            "source": source,
            "upload_batch": upload_batch,
            "status": IocEntry.STATUS_BLOCKED,
            "created_at": timezone.now()
        }
    )
    return ioc, created


def ingest_ioc_to_tool(ioc: IocEntry, tool_name: str, status: str = IocTool.STATUS_INGESTED, detail: Optional[str] = None, user=None):
    """
    Ingesta un IOC en una herramienta *si* la herramienta lo acepta.
    Si no, retorna None (no crea Ingestion).
    """
    ok, reason = validate_tool_accepts_ioc(tool_name, ioc.value)
    if not ok:
        # puedes registrar un Ingestion de intento-fallido si lo deseas:
        # Ingestion.objects.create(ioc=ioc, tool=None, status=Ingestion.STATUS_FAILED, detail=reason, ...)
        return None

    # intentar match exacto y luego parcial
    try:
        tool = Tool.objects.filter(name__iexact=tool_name).first()
        if not tool:
            tool = Tool.objects.filter(name__icontains=tool_name).first()
        if not tool:
            raise Tool.DoesNotExist()
    except Tool.DoesNotExist:
        # si no existe el Tool en DB, no se puede crear ingestion
        return None

    # crear relación IocTool si no existe (o actualizar)
    # merged: create IocTool WITH status
    ingestion, created = IocTool.objects.update_or_create(
        ioc=ioc,
        tool=tool,
        defaults={
            'status': status,
            'ingested_at': timezone.now(),
            'detail': detail
        }
    )
    # History removed
    return ingestion


def generar_txt_ingestions(qs=None):
    """
    Genera contenido tipo TSV para ingestions (ahora IocTool).
    """
    qs = qs or IocTool.objects.select_related("ioc__ioc_type", "tool").order_by("-created_at")[:1000]

    lines = ["id_link\tid_ioc\tioc_value\tioc_type\ttool\tstatus\tingested_at\tcreated_at\tdetail"]

    for ing in qs:
        lines.append(
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}".format(
                ing.pk,
                ing.ioc.pk,
                ing.ioc.value,
                ing.ioc.ioc_type.name if ing.ioc.ioc_type else "",
                ing.tool.name if getattr(ing, "tool", None) else "",
                ing.status,
                ing.ingested_at.isoformat() if ing.ingested_at else "",
                ing.created_at.isoformat() if getattr(ing, "created_at", None) else "",
                (ing.detail or "").replace("\n", " ")
            )
        )

    contenido = "\n".join(lines)
    filename = f"ingestions_{timezone.now().strftime('%Y%m%d%H%M%S')}.txt"
    return filename, contenido

def is_invalid_value(value) -> bool:
    """
    Determina si un valor de IoC es inválido / placeholder / ruido.
    """
    if value is None:
        return True

    try:
        v = str(value).strip()
    except Exception:
        return True

    if not v:
        return True

    INVALID_VALUES = {
        "-", "--", "---", "—",
        "N/A", "NA", "NULL", "NONE",
        "[object Object]"
    }

    if v.upper() in INVALID_VALUES:
        return True

    # líneas solo con símbolos
    if all(c in "-_=*#" for c in v):
        return True

    return False


from django.utils import timezone
from django.db import transaction
from collections import defaultdict

from .models import (
    Tool,
    ToolIndicatorRule,
    ToolHashType,
    IocEntry,
    IocTool,
)

def associate_iocs_with_allowed_tools_bulk(iocs, user=None):
    """
    Asocia IOC ↔ Herramientas válidas en BULK Dinámicamente
    """
    if not iocs:
        return

    now = timezone.now()

    # 🔹 Preload herramientas activas
    active_tools = list(Tool.objects.all())

    # 🔹 Preload reglas ToolIndicatorRule (Diccionario tool_id -> set de nombres de tipos permitidos)
    allowed_rules = defaultdict(set)
    for rule in ToolIndicatorRule.objects.filter(can_ingest=True).select_related('ioc_type'):
        allowed_rules[rule.tool_id].add(rule.ioc_type.name.upper())

    # 🔹 Preload reglas ToolHashType
    allowed_hashes = defaultdict(set)
    for hrule in ToolHashType.objects.select_related('ioc_type'):
        if hrule.ioc_type.name.upper() == "HASH":
            allowed_hashes[hrule.tool_id].add(hrule.algorithm.lower().strip())

    # 🔹 Preload relaciones existentes
    existing_links = set(
        IocTool.objects.filter(ioc__in=iocs)
        .values_list('ioc_id', 'tool_id')
    )

    ioc_tools_to_create = []
    local_added = set()

    for ioc in iocs:
        ioc_type_name = ioc.ioc_type.name.upper()

        for tool in active_tools:
            # 🔒 Validación cruzada Dinámica
            if ioc_type_name not in allowed_rules.get(tool.id, set()):
                continue

            # 🔒 Validación de algoritmo de Hash
            if ioc_type_name == "HASH":
                algo = detect_hash_algorithm(ioc.value)
                if not algo:
                    continue 
                
                tool_hash_algos = allowed_hashes.get(tool.id, set())
                # Si configuró algoritmos y no coincide el detectado, se descarta.
                if tool_hash_algos and algo not in tool_hash_algos:
                    continue

            key = (ioc.id, tool.id)

            if key not in existing_links and key not in local_added:
                ioc_tools_to_create.append(
                    IocTool(
                        ioc=ioc, 
                        tool=tool,
                        status=IocTool.STATUS_INGESTED,
                        ingested_at=now
                    )
                )
                local_added.add(key)

    # 🔥 BULK WRITE
    with transaction.atomic():
        if ioc_tools_to_create:
            IocTool.objects.bulk_create(
                ioc_tools_to_create,
                batch_size=1000
            )



