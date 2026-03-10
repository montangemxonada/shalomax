import time
import logging
from pathlib import Path

import httpx

from app.config import get_settings

log = logging.getLogger("shalomax.pdf")

CACHE_DIR = Path("recibos_cache")
CACHE_DIR.mkdir(exist_ok=True)


async def obtener_pdf_oficial(ose_id: str) -> Path | None:
    settings = get_settings()
    ose_id = str(ose_id).strip()

    if not ose_id.isalnum():
        return None

    pdf = CACHE_DIR / f"{ose_id}.pdf"

    if pdf.exists() and pdf.stat().st_size > 0:
        age = time.time() - pdf.stat().st_mtime
        if age < settings.pdf_cache_ttl:
            return pdf
        pdf.unlink()

    urls = [
        f"{settings.ticket_url}/{ose_id}",
        f"{settings.guia_barra_url}/{ose_id}",
    ]

    async with httpx.AsyncClient(timeout=20) as client:
        for url in urls:
            try:
                r = await client.get(url)
                if r.status_code == 200 and r.content:
                    pdf.write_bytes(r.content)
                    return pdf
            except Exception as e:
                log.warning("Error downloading PDF from %s: %s", url, e)

    return None
