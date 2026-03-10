import logging
import httpx

from app.config import get_settings
from app.services.token import generar_token_bearer_shalom

log = logging.getLogger("shalomax.shalom_api")


async def get_shalom_status(ose_id: str) -> dict:
    settings = get_settings()
    try:
        headers = {
            "Authorization": f"Bearer {generar_token_bearer_shalom()}",
            "Accept": "*/*",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                settings.shalom_api_url,
                data={"ose_id": str(ose_id)},
                headers=headers,
            )
            return r.json() if r.status_code == 200 else {}
    except Exception as e:
        log.warning("Error getting status for OSE %s: %s", ose_id, e)
        return {}


async def buscar_tracking_shalom(
    ose_id: str | None = None,
    numero: str | None = None,
    codigo: str | None = None,
) -> dict:
    settings = get_settings()
    payload = {}
    if ose_id and str(ose_id).strip():
        payload["ose_id"] = str(ose_id).strip()
    if numero and str(numero).strip():
        payload["numero"] = str(numero).strip()
    if codigo and str(codigo).strip():
        payload["codigo"] = str(codigo).strip()

    if not payload:
        return {"success": False, "message": "Debe enviar al menos un parametro de busqueda."}

    try:
        headers = {
            "Authorization": f"Bearer {generar_token_bearer_shalom()}",
            "Accept": "*/*",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                settings.shalom_buscar_url,
                data=payload,
                headers=headers,
            )
            if r.status_code == 200:
                return r.json()
            return {"success": False, "message": f"Error HTTP {r.status_code} en busqueda."}
    except Exception as e:
        log.warning("Error searching Shalom: %s", e)
        return {"success": False, "message": "No se pudo consultar busqueda en Shalom."}


def normalizar_tracking_busqueda(data: dict) -> dict:
    remitente = data.get("remitente", {}) or {}
    destinatario = data.get("destinatario", {}) or {}
    return {
        "service_order_id_empresarial": data.get("ose_id"),
        "service_order_guia_empresarial": data.get("numero_orden"),
        "code_service_order_empresarial": data.get("codigo_orden"),
        "sender_person": {
            "document": remitente.get("documento", ""),
            "full_name": remitente.get("nombre", ""),
        },
        "receiver_person": {
            "document": destinatario.get("documento", ""),
            "full_name": destinatario.get("nombre", ""),
        },
    }
