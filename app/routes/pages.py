from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
import io

from app.services.tracker import search_shipments, get_tracking_detail, mask_dni, estimate_delivery, parse_status_timeline
from app.services.shalom_api import get_shalom_status
from app.services.pdf_service import obtener_pdf_oficial
from app.services.qr_service import generate_qr_png
from app.config import get_settings

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return request.app.state.templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Shalomax - Rastrea tu envío Shalom",
    })


@router.get("/buscar", response_class=HTMLResponse)
async def buscar(request: Request, q: str = "", codigo: str = "", tipo: str = "auto"):
    q = q.strip()
    if not q:
        return RedirectResponse("/", status_code=302)

    result = await search_shipments(q, codigo=codigo, tipo=tipo)
    settings = get_settings()

    enriched_results = []
    if result["success"]:
        for t in result["results"]:
            ose_id = t.get("service_order_id_empresarial")
            if not ose_id:
                continue
            estados = await get_shalom_status(str(ose_id))
            timeline = parse_status_timeline(estados)
            status = estados.get("message", "Sin información") if estados else "Sin información"
            sender = t.get("sender_person", {}) or {}
            receiver = t.get("receiver_person", {}) or {}
            enriched_results.append({
                "ose_id": ose_id,
                "order_number": t.get("service_order_guia_empresarial"),
                "order_code": t.get("code_service_order_empresarial"),
                "sender_name": sender.get("full_name", "No registrado"),
                "sender_dni": mask_dni(sender.get("document", "")),
                "receiver_name": receiver.get("full_name", "No registrado"),
                "receiver_dni": mask_dni(receiver.get("document", "")),
                "status": status,
                "timeline": timeline,
                "estimated_delivery": estimate_delivery(timeline),
            })

    # If single result, redirect to tracking page
    if len(enriched_results) == 1:
        return RedirectResponse(f"/tracking/{enriched_results[0]['ose_id']}", status_code=302)

    return request.app.state.templates.TemplateResponse("results.html", {
        "request": request,
        "title": f"Resultados para '{q}' - Shalomax",
        "query": q,
        "results": enriched_results,
        "source": result.get("source"),
        "message": result.get("message"),
        "success": result["success"],
    })


@router.get("/tracking/{ose_id}", response_class=HTMLResponse)
async def tracking_page(request: Request, ose_id: str):
    settings = get_settings()
    detail = await get_tracking_detail(ose_id)

    tracking = detail.get("tracking") or {}
    sender = tracking.get("sender_person", {}) or {}
    receiver = tracking.get("receiver_person", {}) or {}

    return request.app.state.templates.TemplateResponse("tracking.html", {
        "request": request,
        "title": f"Tracking {ose_id} - Shalomax",
        "ose_id": ose_id,
        "status": detail["status"],
        "timeline": detail["timeline"],
        "has_status": detail["has_status"],
        "sender_name": sender.get("full_name", "No registrado"),
        "sender_dni": mask_dni(sender.get("document", "")),
        "receiver_name": receiver.get("full_name", "No registrado"),
        "receiver_dni": mask_dni(receiver.get("document", "")),
        "order_number": tracking.get("service_order_guia_empresarial", ""),
        "order_code": tracking.get("code_service_order_empresarial", ""),
        "estimated_delivery": estimate_delivery(detail["timeline"]),
        "app_url": settings.app_url,
        "tracking_url": f"{settings.app_url}/tracking/{ose_id}",
    })


@router.get("/recibo/{ose_id}")
async def download_pdf(ose_id: str):
    if not ose_id.isalnum():
        return Response(status_code=400, content="ID inválido")

    pdf_path = await obtener_pdf_oficial(ose_id)
    if not pdf_path:
        return Response(status_code=404, content="No se encontró el recibo PDF")

    content = pdf_path.read_bytes()
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="recibo_{ose_id}.pdf"'},
    )


@router.get("/qr/{ose_id}")
async def qr_code(request: Request, ose_id: str):
    settings = get_settings()
    url = f"{settings.app_url}/tracking/{ose_id}"
    png_bytes = generate_qr_png(url)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/multi", response_class=HTMLResponse)
async def multi_tracking(request: Request, ids: str = ""):
    id_list = [i.strip() for i in ids.split(",") if i.strip()][:10]  # max 10

    if not id_list:
        return request.app.state.templates.TemplateResponse("multi.html", {
            "request": request,
            "title": "Multi-Tracking - Shalomax",
            "trackings": [],
            "ids_str": "",
        })

    trackings = []
    for ose_id in id_list:
        detail = await get_tracking_detail(ose_id)
        tracking = detail.get("tracking") or {}
        sender = tracking.get("sender_person", {}) or {}
        receiver = tracking.get("receiver_person", {}) or {}
        trackings.append({
            "ose_id": ose_id,
            "status": detail["status"],
            "timeline": detail["timeline"],
            "sender_name": sender.get("full_name", "No registrado"),
            "receiver_name": receiver.get("full_name", "No registrado"),
            "estimated_delivery": estimate_delivery(detail["timeline"]),
        })

    return request.app.state.templates.TemplateResponse("multi.html", {
        "request": request,
        "title": "Multi-Tracking - Shalomax",
        "trackings": trackings,
        "ids_str": ids,
    })


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return request.app.state.templates.TemplateResponse("about.html", {
        "request": request,
        "title": "Acerca de - Shalomax",
    })
