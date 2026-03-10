import uuid
import time
import hmac
import hashlib

from app.config import get_settings


def generar_token_bearer_shalom() -> str:
    settings = get_settings()
    prefix = f"web-{uuid.uuid4()}"
    exp = int(time.time()) + 30
    payload = f"{prefix}@{exp}"
    signature = hmac.new(
        settings.shalom_token_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}@{signature}"
