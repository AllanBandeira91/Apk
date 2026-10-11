"""Config central via .env (Shopee)."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    EVOLUTION_API_URL: str = ""
    EVOLUTION_APIKEY: str = ""
    EVOLUTION_INSTANCE: str = "promocoes"
    TARGET_GROUPS: str = ""  # grupo(s): id1@g.us,id2@g.us
    SHOPEE_AFFILIATE_ID: str = ""
    SHOPEE_APPID: str = ""  # Affiliate Open API (nunca commitar o secret)
    SHOPEE_SECRET: str = ""
    SHOPEE_SEARCHES: str = ""  # opcional: "celular,notebook,cadeira gamer" (sobrescreve/complementa a lista padrão)
    # TikTok Shop Partner Center (Affiliate app). Nunca commitar o secret.
    TIKTOK_APP_KEY: str = ""
    TIKTOK_APP_SECRET: str = ""
    TIKTOK_ACCESS_TOKEN: str = ""  # token da loja/criador que autorizou o app (gere 1x no Partner Center)
    TIKTOK_SHOP_CIPHER: str = ""  # opcional: exigido em alguns endpoints de seller
    TIKTOK_SEARCHES: str = ""  # opcional: keywords extras p/ TikTok, separadas por vírgula
    TIKTOK_ENABLED: bool = True
    # Via alternativa SEM CNPJ: Ecomobi (aceita CPF) — busca TikTok/Shopee com comissão.
    # Crie conta grátis em https://ecomobi.com, pegue a API key e cole aqui.
    ECOMOBI_API_KEY: str = ""
    ECOMOBI_ENABLED: bool = True
    SCAN_INTERVAL_MIN: int = 10
    MAX_OFFERS_PER_SCAN: int = 2
    MIN_DISCOUNT_PCT: int = 20

    @property
    def groups(self) -> list[str]:
        return [g.strip() for g in self.TARGET_GROUPS.split(",") if g.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
