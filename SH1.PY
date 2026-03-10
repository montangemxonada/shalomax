# -*- coding: utf-8 -*-
import json
import re
import io
import logging
import os
import uuid
import time
import hmac
import hashlib
import urllib.parse
from pathlib import Path
from functools import wraps
from typing import Optional

import requests

from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===================== CONFIG =====================
TELEGRAM_TOKEN = "8482189125:AAFOUjlEBPXt2NrW63qAbFBmQRhIsA12PCM"

SHALOM_API_URL = "https://serviceswebapi.shalomcontrol.com/api/v1/web/rastrea/estados"
BUSCAR_API_URL = "https://serviceswebapi.shalomcontrol.com/api/v1/web/rastrea/buscar"
SHALOM_TOKEN_SECRET = ".Ov3rsku112024l4r43l."
PRO_BASE_URL = "https://pro.shalom.pe"
PRO_LOGIN_URL = f"{PRO_BASE_URL}/login"
PRO_TRACKING_URL = f"{PRO_BASE_URL}/tracking-shipment"
PRO_LOGIN_EMAIL = os.getenv("SHALOM_PRO_EMAIL", "XSEBASTIANX088@gmail.com")
PRO_LOGIN_PASSWORD = os.getenv("SHALOM_PRO_PASSWORD", "sebas1212")
PRO_CACHE_TTL_SECONDS = 180
BLOCKED_DNIS = {"74780704"}
ICON_PACKAGE = "PAQ"
ICON_OK = "OK"
ICON_PENDING = "PEND"
ICON_DENIED = "DENEGADO"
ICON_BOT = "BOT"

ALLOWED_TELEGRAM_IDS = {2029290365, -1001945809003}

PDF_CACHE_TTL_SECONDS = 86400  # 24 horas
GUIA_BARRA_URL = "https://syslima.shalomcontrol.com/imprimirguiabarra"

CACHE_DIR = Path("recibos_cache")
CACHE_DIR.mkdir(exist_ok=True)

MANUAL_FILE = Path("manual.txt")
if not MANUAL_FILE.exists():
    MANUAL_FILE.write_text("[]", encoding="utf-8")
# ==================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("shalom-bot")
_pro_trackings_cache = {"expires_at": 0.0, "data": []}

# ===================== MARKDOWN HELPERS =====================

def escape_md_v2(text: str) -> str:
    if text is None:
        return ""
    return re.sub(r'([\\_*[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

def md(x) -> str:
    return escape_md_v2("" if x is None else str(x))

def is_blocked_dni(dni: str) -> bool:
    normalized = re.sub(r"\D", "", str(dni or ""))
    return normalized in BLOCKED_DNIS

# ===================== DATA HELPERS =====================

def load_trackings():
    files = [
        "pendientespatrick.txt",
        "trackings.txt",
        "patrick.txt",
        "entregados.txt",
        "entregadospatrick.txt",
        "manual.txt",
    ]
    result = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    result.extend(data)
        except Exception:
            pass
    return result

def find_tracking(query):
    query = str(query).strip()
    res = []
    for t in load_trackings():
        sender = t.get("sender_person", {}) or {}
        receiver = t.get("receiver_person", {}) or {}
        if query in [
            str(sender.get("document", "")).strip(),
            str(receiver.get("document", "")).strip(),
            str(t.get("service_order_id_empresarial", "")).strip(),
            str(t.get("service_order_guia_empresarial", "")).strip(),
        ]:
            res.append(t)
    return res

def _login_pro_session():
    s = requests.Session()
    page = s.get(PRO_LOGIN_URL, timeout=20)
    if page.status_code != 200:
        raise RuntimeError(f"No se pudo abrir login PRO (HTTP {page.status_code})")

    m = re.search(r'name="_token"\s+value="([^"]+)"', page.text)
    if not m:
        raise RuntimeError("No se pudo obtener CSRF de login PRO.")
    csrf_token = m.group(1)

    payload = {
        "_token": csrf_token,
        "email": PRO_LOGIN_EMAIL,
        "password": PRO_LOGIN_PASSWORD,
        "remember": "on",
    }
    headers = {
        "Referer": PRO_LOGIN_URL,
        "Origin": PRO_BASE_URL,
        "User-Agent": "Mozilla/5.0",
    }
    s.post(PRO_LOGIN_URL, data=payload, headers=headers, allow_redirects=True, timeout=20)

    session_cookie = s.cookies.get("enviashalom_session")
    if not session_cookie:
        raise RuntimeError("No se inicio sesion en PRO (cookie de sesion ausente).")

    xsrf_cookie = s.cookies.get("XSRF-TOKEN", "")
    xsrf_token = urllib.parse.unquote(xsrf_cookie) if xsrf_cookie else csrf_token
    return s, xsrf_token

def get_trackings_pro(force_refresh=False):
    now = time.time()
    if not force_refresh and _pro_trackings_cache["data"] and _pro_trackings_cache["expires_at"] > now:
        return _pro_trackings_cache["data"]

    try:
        s, xsrf = _login_pro_session()
        headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{PRO_BASE_URL}/",
            "Origin": PRO_BASE_URL,
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json;charset=UTF-8",
            "X-XSRF-TOKEN": xsrf,
        }
        r = s.post(PRO_TRACKING_URL, data="{}", headers=headers, timeout=25)
        if r.status_code != 200:
            log.warning("tracking-shipment devolvio HTTP %s", r.status_code)
            return []

        data = r.json()
        if isinstance(data, list):
            _pro_trackings_cache["data"] = data
            _pro_trackings_cache["expires_at"] = now + PRO_CACHE_TTL_SECONDS
            return data

        log.warning("tracking-shipment no devolvio lista.")
        return []
    except Exception as e:
        log.warning("No se pudo consultar PRO tracking: %s", e)
        return []

def find_tracking_pro(query, force_refresh=False):
    query = str(query).strip()
    res = []
    for t in get_trackings_pro(force_refresh=force_refresh):
        sender = t.get("sender_person", {}) or {}
        receiver = t.get("receiver_person", {}) or {}
        if query in [
            str(sender.get("document", "")).strip(),
            str(receiver.get("document", "")).strip(),
            str(t.get("service_order_id_empresarial", "")).strip(),
            str(t.get("service_order_guia_empresarial", "")).strip(),
        ]:
            res.append(t)
    return res

def generar_token_bearer_shalom() -> str:
    prefix = f"web-{uuid.uuid4()}"
    exp = int(time.time()) + 30
    payload = f"{prefix}@{exp}"
    signature = hmac.new(
        SHALOM_TOKEN_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}@{signature}"

def get_shalom_status(ose_id):
    try:
        headers = {
            "Authorization": f"Bearer {generar_token_bearer_shalom()}",
            "Accept": "*/*",
        }
        files = {"ose_id": (None, str(ose_id))}
        r = requests.post(SHALOM_API_URL, headers=headers, files=files, timeout=15)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def buscar_tracking_shalom(ose_id=None, numero=None, codigo=None):
    payload = {}
    if ose_id is not None and str(ose_id).strip():
        payload["ose_id"] = str(ose_id).strip()
    if numero is not None and str(numero).strip():
        payload["numero"] = str(numero).strip()
    if codigo is not None and str(codigo).strip():
        payload["codigo"] = str(codigo).strip()

    if not payload:
        return {"success": False, "message": "Debe enviar al menos un parametro de busqueda."}

    try:
        headers = {
            "Authorization": f"Bearer {generar_token_bearer_shalom()}",
            "Accept": "*/*",
        }
        files = {k: (None, v) for k, v in payload.items()}
        r = requests.post(BUSCAR_API_URL, headers=headers, files=files, timeout=15)
        if r.status_code == 200:
            return r.json()
        return {
            "success": False,
            "message": f"Error HTTP {r.status_code} en busqueda.",
        }
    except Exception:
        return {"success": False, "message": "No se pudo consultar busqueda en Shalom."}

def normalizar_tracking_busqueda(data):
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

def obtener_pdf_oficial(ose_id: str) -> Optional[Path]:
    pdf = CACHE_DIR / f"{ose_id}.pdf"
    if pdf.exists() and pdf.stat().st_size > 0:
        age = time.time() - pdf.stat().st_mtime
        if age < PDF_CACHE_TTL_SECONDS:
            return pdf
        pdf.unlink()
    try:
        r = requests.get(f"https://syslima.shalomcontrol.com/ticket_os/{ose_id}", timeout=20)
        if r.status_code == 200 and r.content:
            pdf.write_bytes(r.content)
            return pdf
    except Exception:
        pass
    try:
        r = requests.get(f"{GUIA_BARRA_URL}/{ose_id}", timeout=20)
        if r.status_code == 200 and r.content:
            pdf.write_bytes(r.content)
            return pdf
    except Exception:
        pass
    return None

async def enviar_tracking(update: Update, tracking: dict, i: int, total: int):
    ose = tracking.get("service_order_id_empresarial")
    if not ose:
        await update.message.reply_text(
            md("No se encontro OSE para el envio."),
            parse_mode="MarkdownV2"
        )
        return

    estados = get_shalom_status(ose)
    pdf = obtener_pdf_oficial(str(ose))

    if not pdf:
        await update.message.reply_text(
            md(f"No se pudo descargar PDF de OSE {ose}"),
            parse_mode="MarkdownV2"
        )
        return

    caption = build_caption_md(tracking, estados, i, total)
    with open(pdf, "rb") as f:
        await update.message.reply_document(
            document=InputFile(io.BytesIO(f.read()), filename=f"recibo_{ose}.pdf"),
            caption=caption,
            parse_mode="MarkdownV2",
            disable_content_type_detection=True
        )

# ===================== CAPTION =====================

def _fecha_estado(data: dict, key: str) -> Optional[str]:
    node = data.get(key)
    if isinstance(node, dict) and node.get("fecha"):
        return str(node["fecha"])
    return None

def resumir_estados_md(estados) -> str:
    if not estados or "data" not in estados:
        return "_Sin eventos de estado disponibles\\._"

    data = estados.get("data", {}) or {}
    estado_actual = md(estados.get("message", "Sin informacion"))
    etapas = [
        ("registrado", "Registrado"),
        ("origen", "En origen"),
        ("transito", "En transito"),
        ("destino", "En destino"),
        ("reparto", "En reparto"),
        ("entregado", "Entregado"),
    ]
    lines = [
        f"{ICON_PACKAGE} *Estado actual:* *{estado_actual}*",
        "",
        "*Linea de tiempo:*",
    ]
    for idx, (key, label) in enumerate(etapas, start=1):
        fecha = _fecha_estado(data, key)
        if fecha:
            lines.append(f"{idx}\\. {ICON_OK} *{md(label)}:* {md(fecha)}")
        else:
            lines.append(f"{idx}\\. {ICON_PENDING} *{md(label)}:* _Pendiente_")
    return "\n".join(lines)

def build_caption_md(tracking, estados, i, total) -> str:
    sender = tracking.get("sender_person", {}) or {}
    receiver = tracking.get("receiver_person", {}) or {}

    return (
        f"{ICON_PACKAGE} *Resultado {i}/{total}*\n"
        f"\n"
        f"*OSE ID:* `{md(tracking.get('service_order_id_empresarial'))}`\n"
        f"*Orden:* `{md(tracking.get('service_order_guia_empresarial'))}`\n"
        f"*Codigo:* `{md(tracking.get('code_service_order_empresarial'))}`\n"
        f"*Remitente:* {md(sender.get('full_name', 'No registrado'))}\n"
        f"*Destinatario:* {md(receiver.get('full_name', 'No registrado'))}\n"
        f"\n"
        f"{resumir_estados_md(estados)}"
    )
# ===================== SECURITY =====================

def restricted(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        cid = update.effective_chat.id
        if uid not in ALLOWED_TELEGRAM_IDS and cid not in ALLOWED_TELEGRAM_IDS:
            await update.message.reply_text(f"{ICON_DENIED} Sin permiso.")
            return
        return await func(update, context)
    return wrapper

# ===================== COMMANDS =====================

@restricted
async def handle_shdni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /shdni [dni]")
        return

    dni = str(context.args[0]).strip()
    if is_blocked_dni(dni):
        await update.message.reply_text("Ese DNI esta bloqueado para consulta por volumen.")
        return

    results = find_tracking(dni)
    source = "local"

    if not results:
        results = find_tracking_pro(dni)
        source = "pro"

    if not results:
        await update.message.reply_text(
            md(f"No se encontro ningun envio con DNI {dni}"),
            parse_mode="MarkdownV2"
        )
        return

    if source == "pro":
        await update.message.reply_text(
            md("Se usaron envios en vivo desde PRO."),
            parse_mode="MarkdownV2"
        )

    for i, tracking in enumerate(results, start=1):
        await enviar_tracking(update, tracking, i, len(results))

@restricted
async def handle_shprodni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /shprodni [dni]")
        return

    dni = str(context.args[0]).strip()
    if is_blocked_dni(dni):
        await update.message.reply_text("Ese DNI esta bloqueado para consulta por volumen.")
        return

    results = find_tracking_pro(dni, force_refresh=True)
    if not results:
        await update.message.reply_text(
            md(f"No se encontro ningun envio PRO con DNI {dni}"),
            parse_mode="MarkdownV2"
        )
        return

    for i, tracking in enumerate(results, start=1):
        await enviar_tracking(update, tracking, i, len(results))

@restricted
async def handle_shose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /shose [ose_id]")
        return

    ose_id = str(context.args[0]).strip()
    data = buscar_tracking_shalom(ose_id=ose_id)
    if not data.get("success") or not data.get("data"):
        await update.message.reply_text(
            md(data.get("message", f"No se encontro OSE {ose_id}")),
            parse_mode="MarkdownV2"
        )
        return

    tracking = normalizar_tracking_busqueda(data["data"])
    await enviar_tracking(update, tracking, 1, 1)

@restricted
async def handle_shorden(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /shorden [numero_orden] [codigo_orden]")
        return

    numero = str(context.args[0]).strip()
    codigo = str(context.args[1]).strip().upper()

    data = buscar_tracking_shalom(numero=numero, codigo=codigo)
    if not data.get("success") or not data.get("data"):
        await update.message.reply_text(
            md(data.get("message", f"No se encontro orden {numero} / {codigo}")),
            parse_mode="MarkdownV2"
        )
        return

    tracking = normalizar_tracking_busqueda(data["data"])
    await enviar_tracking(update, tracking, 1, 1)

@restricted
async def handle_shguia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /shguia [numero_guia]")
        return

    nroguia = str(context.args[0]).strip()

    # 1. Buscar en archivos locales por numero de guia
    results = find_tracking(nroguia)
    source = "local"

    # 2. Buscar en PRO por numero de guia
    if not results:
        results = find_tracking_pro(nroguia)
        source = "pro"

    # 3. Intentar con la API publica (solo numero, sin codigo)
    if not results:
        data = buscar_tracking_shalom(numero=nroguia)
        if data.get("success") and data.get("data"):
            results = [normalizar_tracking_busqueda(data["data"])]
            source = "api"

    if not results:
        await update.message.reply_text(
            md(f"No se encontro ningun envio con numero de guia {nroguia}"),
            parse_mode="MarkdownV2"
        )
        return

    if source == "pro":
        await update.message.reply_text(
            md("Se usaron envios en vivo desde PRO."),
            parse_mode="MarkdownV2"
        )

    for i, tracking in enumerate(results, start=1):
        await enviar_tracking(update, tracking, i, len(results))

@restricted
async def handle_shstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Uso: /shstatus [ose_id]")
        return

    ose_id = str(context.args[0]).strip()
    estados = get_shalom_status(ose_id)
    if not estados or "data" not in estados:
        await update.message.reply_text(
            md(f"No se pudo obtener estado para OSE {ose_id}"),
            parse_mode="MarkdownV2"
        )
        return

    texto = (
        f"{ICON_PACKAGE} *Estado OSE:* `{md(ose_id)}`\n"
        f"\n"
        f"{resumir_estados_md(estados)}"
    )
    await update.message.reply_text(texto, parse_mode="MarkdownV2")

# ===================== MAIN =====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Error no controlado", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("Ocurrio un error procesando la solicitud.")
    except Exception:
        pass

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("shdni", handle_shdni))
    app.add_handler(CommandHandler("shprodni", handle_shprodni))
    app.add_handler(CommandHandler("shose", handle_shose))
    app.add_handler(CommandHandler("shorden", handle_shorden))
    app.add_handler(CommandHandler("shguia", handle_shguia))
    app.add_handler(CommandHandler("shstatus", handle_shstatus))
    app.add_error_handler(error_handler)
    print(f"{ICON_BOT} Bot iniciado correctamente")
    app.run_polling()

if __name__ == "__main__":
    main()

