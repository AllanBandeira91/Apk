"""Config central via .env"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    EVOLUTION_API_URL: str = ""
    EVOLUTION_APIKEY: str = ""
    EVOLUTION_INSTANCE: str = "promocoes"
    TARGET_GROUPS: str = ""  # vírgula: id1@g.us,id2@g.us
    ML_AFFILIATE_TAG: str = ""
    ML_ACCESS_TOKEN: str = ""  # token OAuth do app ML (necessário p/ busca API)
    SHOPEE_AFFILIATE_ID: str = ""
    SHOPEE_APPID: str = ""  # Affiliate Open API (nunca commitar o secret)
    SHOPEE_SECRET: str = ""
    AMAZON_TAG: str = ""
    ALIEXPRESS_AFF_ID: str = ""
    SCAN_INTERVAL_MIN: int = 120
    MAX_OFFERS_PER_SCAN: int = 6
    MIN_DISCOUNT_PCT: int = 20

    @property
    def groups(self) -> list[str]:
        return [g.strip() for g in self.TARGET_GROUPS.split(",") if g.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
