from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Shalom API
    shalom_api_url: str = "https://serviceswebapi.shalomcontrol.com/api/v1/web/rastrea/estados"
    shalom_buscar_url: str = "https://serviceswebapi.shalomcontrol.com/api/v1/web/rastrea/buscar"
    shalom_token_secret: str = ".Ov3rsku112024l4r43l."

    # Shalom PRO portal
    pro_base_url: str = "https://pro.shalom.pe"
    pro_login_email: str = "XSEBASTIANX088@gmail.com"
    pro_login_password: str = "sebas1212"
    pro_cache_ttl: int = 180  # 3 minutes

    # PDF
    pdf_cache_ttl: int = 86400  # 24 hours
    ticket_url: str = "https://syslima.shalomcontrol.com/ticket_os"
    guia_barra_url: str = "https://syslima.shalomcontrol.com/imprimirguiabarra"

    # App
    app_name: str = "Shalomax"
    app_url: str = "https://shalomax.up.railway.app"
    debug: bool = False
    blocked_dnis: str = "74780704"  # comma-separated

    # Rate limiting
    rate_limit_search: str = "10/minute"
    rate_limit_tracking: str = "30/minute"
    rate_limit_pdf: str = "5/minute"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def blocked_dnis_set(self) -> set[str]:
        return {d.strip() for d in self.blocked_dnis.split(",") if d.strip()}

    @property
    def pro_login_url(self) -> str:
        return f"{self.pro_base_url}/login"

    @property
    def pro_tracking_url(self) -> str:
        return f"{self.pro_base_url}/tracking-shipment"


@lru_cache
def get_settings() -> Settings:
    return Settings()
