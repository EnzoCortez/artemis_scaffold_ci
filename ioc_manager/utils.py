# ioc_manager/utils.py
import re
from typing import Optional, Tuple
from django.utils import timezone
from .models import IocEntry, IocType, Tool, Ingestion

# ==========================================================
# 1. DETECTORES DE IOC (robustos)
# ==========================================================

_RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_RE_IPV4 = re.compile(r"^(25[0-5]|2[0-4]\d|1?\d{1,2})(\.(25[0-5]|2[0-4]\d|1?\d{1,2})){3}$")
_RE_IPV6 = re.compile(r"^([0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}$")
# dominio simple (sin path)
_RE_DOMAIN = re.compile(r"^(?!:\/\/)([A-Za-z0-9\-]{1,63}\.)+[A-Za-z]{2,63}$")
# URL robusta: acepta con o sin protocolo, subdominios, puerto opcional y rutas
_RE_URL = re.compile(r"^(?:https?:\/\/)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:\:[0-9]{1,5})?(?:\/[^\s]*)?$")
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


def detect_ioc_type(value: str) -> Optional[str]:
    """
    Devuelve uno de los tipos conocidos:
    - "Hash", "IP", "Dominio", "URL", "Correo"
    Si no puede determinar, retorna None.
    """
    if not value:
        return None
    v = value.strip()

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
        # validamos con la regex robusta
        if _RE_URL.fullmatch(v):
            return "URL"
        # aún si no pasa regex completa, considerarlo URL por protocolo
        return "URL"

    # URL implícita: tiene "/" y la parte izquierda es un dominio válido
    if "/" in v:
        left = v.split("/", 1)[0]
        if _RE_DOMAIN.fullmatch(left) or re.fullmatch(r"[A-Za-z0-9\-.]+\.[A-Za-z]{2,}", left):
            # validar con la regex completa también
            if _RE_URL.fullmatch(v):
                return "URL"
            return "URL"

    # Dominio simple
    if _RE_DOMAIN.fullmatch(v) or re.fullmatch(r"[A-Za-z0-9\-.]+\.[A-Za-z]{2,}", v):
        return "Dominio"

    return None


# ==========================================================
# 2. MATRIZ DE HERRAMIENTAS (TODAS ACEPTAN IP)
#    Las claves aquí son *canonical names* (mayúsculas para normalizar).
# ==========================================================

_VALID_TOOL_IOCTYPES = {
    "EDR (CROWDSTRIKE)": {
        "types": {"IP", "Hash"},
        "hash_algos": {"md5", "sha256"},
    },
    "IPS": {
        "types": {"IP", "Hash", "URL"},
        "hash_algos": {"md5", "sha1", "sha256"},
    },
    "FIREWALL": {
        "types": {"IP", "Dominio", "URL"},
        "hash_algos": set()
    },
    "FTD": {
        "types": {"IP", "Dominio"},
        "hash_algos": set()
    },
    "MERAKI": {
        "types": {"IP", "URL"},
        "hash_algos": set()
    },
    "PROXY": {
        "types": {"IP", "Dominio", "URL"},
        "hash_algos": set()
    },
    "PROOFPOINT": {
        "types": {"Correo", "URL", "IP"},
        "hash_algos": set()
    }
}


def normalize_tool(tool_name: str) -> str:
    """Normaliza nombres: strip + upper"""
    return (tool_name or "").strip().upper()


def resolve_tool_key(tool_name: str) -> Optional[str]:
    """
    Resuelve el nombre provisto a la clave canonical en _VALID_TOOL_IOCTYPES.
    Hace matching flexible (contains / startswith / equal).
    """
    if not tool_name:
        return None
    norm = normalize_tool(tool_name)
    # match exact
    if norm in _VALID_TOOL_IOCTYPES:
        return norm
    # try to find key that contains norm or viceversa
    for key in _VALID_TOOL_IOCTYPES.keys():
        key_up = key.upper()
        if norm == key_up or norm in key_up or key_up in norm:
            return key
    return None


def validate_tool_accepts_ioc(tool_name: str, value: str) -> Tuple[bool, Optional[str]]:
    """
    Valida si una herramienta puede ingerir un IOC.
    Retorna: (True, None) si se puede
             (False, "motivo") si NO se permite
    """
    tipo = detect_ioc_type(value)
    if not tipo:
        return False, f"No se reconoce el tipo de IOC para '{value}'."

    # resolver clave canonical
    key = resolve_tool_key(tool_name)
    if not key:
        return False, f"Herramienta '{tool_name}' no está configurada."

    cfg = _VALID_TOOL_IOCTYPES[key]

    # todas aceptan IP → forzamos True si tipo es IP
    if tipo == "IP":
        return True, None

    # tipo permitido?
    if tipo not in cfg["types"]:
        return False, f"'{tool_name}' no acepta IOC de tipo {tipo}."

    # si es Hash, validar algoritmo
    if tipo == "Hash":
        algo = detect_hash_algorithm(value)
        if not algo:
            return False, "Hash inválido."
        if cfg["hash_algos"] and algo not in cfg["hash_algos"]:
            return False, f"'{tool_name}' solo acepta hashes: {', '.join(sorted(cfg['hash_algos']))}."

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


def ingest_ioc_to_tool(ioc: IocEntry, tool_name: str, status: str = Ingestion.STATUS_INGESTED, detail: Optional[str] = None, user=None):
    """
    Ingesta un IOC en una herramienta *si* la herramienta lo acepta.
    Si no, retorna None (no crea Ingestion).
    """
    ok, reason = validate_tool_accepts_ioc(tool_name, ioc.value)
    if not ok:
        # puedes registrar un Ingestion de intento-fallido si lo deseas:
        # Ingestion.objects.create(ioc=ioc, tool=None, status=Ingestion.STATUS_FAILED, detail=reason, ...)
        return None

    # resolver el Tool real por su nombre (intentar match exacto y flexible)
    try:
        # primer intento: exact match (insensible a mayúsculas)
        tool = Tool.objects.filter(name__iexact=tool_name).first()
        if not tool:
            # intentar resolver por contains
            tool = Tool.objects.filter(name__icontains=tool_name).first()
        if not tool:
            # fallback: buscar por resolved key en _VALID_TOOL_IOCTYPES
            key = resolve_tool_key(tool_name)
            if key:
                # buscar tool cuyo nombre contenga key (case-insensitive)
                tool = Tool.objects.filter(name__icontains=key.split()[0]).first()
        if not tool:
            raise Tool.DoesNotExist()
    except Tool.DoesNotExist:
        # si no existe el Tool en DB, no se puede crear ingestion
        return None

    ingestion = ioc.register_ingestion(
        tool=tool,
        status=status,
        ingested_at=timezone.now(),
        extra_comment=detail,
        user=user
    )
    return ingestion


def generar_txt_ingestions(qs=None):
    """
    Genera contenido tipo TSV para ingestions.
    """
    qs = qs or Ingestion.objects.select_related("ioc__ioc_type", "tool").order_by("-created_at")[:1000]

    lines = ["id_ingestion\tid_ioc\tioc_value\tioc_type\ttool\tstatus\tingested_at\tcreated_at\tdetail"]

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
