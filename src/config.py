"""Config central via .env"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    EVOLUTION_API_URL: str = ""
    EVOLUTION_APIKEY: str = ""
    EVOLUTION_INSTANCE: str = "promocoes"
    TARGET_GROUPS: str = ""  # grupo(s) Shopee: id1@g.us,id2@g.us
    ML_GROUPS: str = ""  # grupo(s) Mercado Livre: id@g.us
    ML_AFFILIATE_TAG: str = ""
    ML_CLIENT_ID: str = ""  # OAuth ML (renovação automática do token)
    ML_CLIENT_SECRET: str = ""
    ML_REFRESH_TOKEN: str = ""  # colado 1x via /callback, bot renova sozinho
    SHOPEE_AFFILIATE_ID: str = ""
    SHOPEE_APPID: str = ""  # Affiliate Open API (nunca commitar o secret)
    SHOPEE_SECRET: str = ""
    AMAZON_TAG: str = ""
    ALIEXPRESS_AFF_ID: str = ""
    SCAN_INTERVAL_MIN: int = 10
    MAX_OFFERS_PER_SCAN: int = 2
    MIN_DISCOUNT_PCT: int = 20

    @property
    def groups(self) -> list[str]:
        return [g.strip() for g in self.TARGET_GROUPS.split(",") if g.strip()]

    @property
    def ml_groups(self) -> list[str]:
        return [g.strip() for g in self.ML_GROUPS.split(",") if g.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
