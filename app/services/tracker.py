import re
import logging

from app.config import get_settings
from app.services.shalom_api import get_shalom_status, buscar_tracking_shalom, normalizar_tracking_busqueda

log = logging.getLogger("shalomax.tracker")

ETAPAS = [
    ("registrado", "Registrado"),
    ("origen", "En origen"),
    ("transito", "En tránsito"),
    ("destino", "En destino"),
    ("reparto", "En reparto"),
    ("entregado", "Entregado"),
]


def detect_query_type(query: str) -> str:
    query = query.strip()
    if re.match(r"^\d{8}$", query):
        return "dni"
    if re.match(r"^\d{5,7}$", query):
        return "ose"
    if re.match(r"^[A-Za-z]{2,4}\d+", query):
        return "guia"
    return "auto"


def mask_dni(dni: str) -> str:
    dni = str(dni or "").strip()
    if len(dni) >= 6:
        return "****" + dni[-4:]
    return dni


def is_blocked_dni(dni: str) -> bool:
    settings = get_settings()
    normalized = re.sub(r"\D", "", str(dni or ""))
    return normalized in settings.blocked_dnis_set


def parse_status_timeline(estados: dict) -> list[dict]:
    if not estados or "data" not in estados:
        return [
            {"step": key, "label": label, "date": None, "completed": False}
            for key, label in ETAPAS
        ]

    data = estados.get("data", {}) or {}
    timeline = []
    for key, label in ETAPAS:
        node = data.get(key)
        fecha = None
        if isinstance(node, dict) and node.get("fecha"):
            fecha = str(node["fecha"])
        timeline.append({
            "step": key,
            "label": label,
            "date": fecha,
            "completed": fecha is not None,
        })
    return timeline


def get_current_status(estados: dict) -> str:
    if estados and estados.get("message"):
        return str(estados["message"])
    return "Sin información"


async def search_shipments(query: str, codigo: str = "", tipo: str = "auto") -> dict:
    query = query.strip()
    codigo = codigo.strip().upper()

    if not query:
        return {"success": False, "results": [], "source": None, "message": "Ingresa un término de búsqueda."}

    if is_blocked_dni(query):
        return {"success": False, "results": [], "source": None, "message": "Este DNI está bloqueado para consultas."}

    # Búsqueda por tipo específico
    if tipo == "ose":
        return await _search_by_ose(query)
    elif tipo == "orden":
        return await _search_by_orden(query, codigo)

    # Auto-detect: probar como OSE primero, luego como orden
    result = await _search_by_ose(query)
    if result["success"]:
        return result

    result = await _search_by_orden(query, codigo)
    if result["success"]:
        return result

    return {
        "success": False,
        "results": [],
        "source": None,
        "message": f"No se encontró ningún envío con '{query}'.",
    }


async def _search_by_ose(query: str) -> dict:
    try:
        data = await buscar_tracking_shalom(ose_id=query)
        if data.get("success") and data.get("data"):
            return {
                "success": True,
                "results": [normalizar_tracking_busqueda(data["data"])],
                "source": "api",
                "message": None,
            }
    except Exception as e:
        log.warning("OSE search failed: %s", e)
    return {"success": False, "results": [], "source": None, "message": f"No se encontró OSE '{query}'."}


async def _search_by_orden(query: str, codigo: str = "") -> dict:
    try:
        data = await buscar_tracking_shalom(numero=query, codigo=codigo if codigo else None)
        if data.get("success") and data.get("data"):
            return {
                "success": True,
                "results": [normalizar_tracking_busqueda(data["data"])],
                "source": "api",
                "message": None,
            }
    except Exception as e:
        log.warning("Orden search failed: %s", e)
    return {"success": False, "results": [], "source": None, "message": f"No se encontró orden '{query}'."}


async def get_tracking_detail(ose_id: str) -> dict:
    # Get status
    estados = await get_shalom_status(ose_id)
    timeline = parse_status_timeline(estados)
    current_status = get_current_status(estados)

    # Try to get tracking info from API
    tracking_info = None
    data = await buscar_tracking_shalom(ose_id=ose_id)
    if data.get("success") and data.get("data"):
        tracking_info = normalizar_tracking_busqueda(data["data"])

    return {
        "ose_id": ose_id,
        "tracking": tracking_info,
        "status": current_status,
        "timeline": timeline,
        "has_status": bool(estados and "data" in estados),
    }


def estimate_delivery(timeline: list[dict]) -> str | None:
    completed_count = sum(1 for step in timeline if step["completed"])
    total = len(timeline)

    if completed_count == 0:
        return None
    if completed_count >= total:
        return "Entregado"

    remaining = total - completed_count
    if remaining == 1:
        return "Próximamente"
    elif remaining == 2:
        return "1-2 días"
    elif remaining == 3:
        return "2-3 días"
    else:
        return "3-5 días"
