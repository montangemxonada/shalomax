from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.models.tracking import SearchRequest, SearchResponse, TrackingResult, PersonInfo, TimelineStep
from app.services.tracker import search_shipments, get_tracking_detail, mask_dni, estimate_delivery, parse_status_timeline
from app.services.shalom_api import get_shalom_status
from app.services.pdf_service import obtener_pdf_oficial
from app.services.qr_service import generate_qr_png
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["api"])


def _build_tracking_result(tracking: dict, status: str, timeline: list[dict], app_url: str) -> TrackingResult:
    sender = tracking.get("sender_person", {}) or {}
    receiver = tracking.get("receiver_person", {}) or {}
    ose_id = str(tracking.get("service_order_id_empresarial", ""))
    steps = [TimelineStep(**s) for s in timeline]

    return TrackingResult(
        ose_id=ose_id,
        order_number=tracking.get("service_order_guia_empresarial"),
        order_code=tracking.get("code_service_order_empresarial"),
        sender=PersonInfo(
            document=mask_dni(sender.get("document", "")),
            full_name=sender.get("full_name", "No registrado"),
        ),
        receiver=PersonInfo(
            document=mask_dni(receiver.get("document", "")),
            full_name=receiver.get("full_name", "No registrado"),
        ),
        status=status,
        timeline=steps,
        tracking_url=f"{app_url}/tracking/{ose_id}",
        estimated_delivery=estimate_delivery(timeline),
    )


@router.post("/search", response_model=SearchResponse)
async def api_search(body: SearchRequest):
    settings = get_settings()
    result = await search_shipments(body.query, codigo=body.codigo, tipo=body.tipo)

    if not result["success"]:
        return SearchResponse(success=False, message=result["message"])

    tracking_results = []
    for t in result["results"]:
        ose_id = t.get("service_order_id_empresarial")
        if not ose_id:
            continue
        estados = await get_shalom_status(str(ose_id))
        timeline = parse_status_timeline(estados)
        status = estados.get("message", "Sin información") if estados else "Sin información"
        tracking_results.append(_build_tracking_result(t, status, timeline, settings.app_url))

    return SearchResponse(
        success=True,
        count=len(tracking_results),
        source=result["source"],
        results=tracking_results,
    )


@router.get("/tracking/{ose_id}")
async def api_tracking_detail(ose_id: str):
    settings = get_settings()
    detail = await get_tracking_detail(ose_id)

    if detail["tracking"]:
        result = _build_tracking_result(
            detail["tracking"], detail["status"], detail["timeline"], settings.app_url
        )
        return result.model_dump()

    return {
        "ose_id": ose_id,
        "status": detail["status"],
        "timeline": detail["timeline"],
        "has_status": detail["has_status"],
    }


@router.get("/tracking/{ose_id}/status")
async def api_tracking_status(ose_id: str):
    estados = await get_shalom_status(ose_id)
    timeline = parse_status_timeline(estados)
    return {
        "ose_id": ose_id,
        "status": estados.get("message", "Sin información") if estados else "Sin información",
        "timeline": timeline,
    }


@router.get("/health")
async def health():
    return {"status": "ok", "app": "shalomax"}
