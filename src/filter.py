"""Modelo + filtro nicho: roupa modesta/evangélica + brinquedos."""
from dataclasses import dataclass

@dataclass
class Offer:
    title: str
    price: float
    original_price: float | None
    url: str
    image: str
    source: str  # ml | shopee | amazon | aliexpress
    category: str = ""  # moda | brinquedos

    @property
    def discount_pct(self) -> float:
        if not self.original_price or self.original_price <= self.price or self.original_price <= 0:
            return 0.0
        return round((1 - self.price / self.original_price) * 100, 1)

# Termos que APROVAM roupa modesta
MODESTA_OK = [
    "vestido longo", "vestido midi", "vestido evangélica", "vestido evangelica",
    "saia longa", "saia midi", "saia evangélica", "conjunto modesto",
    "blusa social", "camisa social feminina", "blazer feminino",
    "vestido godê", "vestido plus size longo", "saia plissada",
    "midi", "longo", "godê", "ciganinha com manga", "manga longa",
    "conjunto saia e blusa", "macacão longo", "pantalona",
]

# Termos que REPROVAM (não é perfil crente)
MODESTA_BLOCK = [
    "mini saia", "minissaia", "short jeans curto", "cropped", "tomara que caia",
    "decote profundo", "fenda alta", "body cavado", "biquini", "biquíni",
    "maiô cavado", "lingerie", "transparente", "tubinho curto",
]

BRINQ_OK = [
    "lego", "barbie", "carrinho", "boneca", "quebra-cabeça", "quebra cabeça",
    "jogo educativo", "massinha", "play doh", "hot wheels", "pelúcia",
    "patinete", "bicicleta infantil", "blocos de montar", "dinossauro brinquedo",
    "cozinha infantil", "baby alive", "nerf", "pista",
]

BRINQ_BLOCK = ["colecionável adulto", "funko pop raro", "+18", "airsoft", "arma de pressão"]


def classify(title: str) -> str | None:
    """Retorna 'moda' | 'brinquedos' | None (rejeitado)."""
    t = title.lower()

    if any(b in t for b in MODESTA_BLOCK + BRINQ_BLOCK):
        return None

    is_moda = any(k in t for k in MODESTA_OK) or any(
        w in t for w in ["vestido", "saia", "blusa feminina", "conjunto feminino", "macacão feminino"]
    )
    # Evita vestido de festa curto transparente etc: exige sinal de modéstia OU tamanho plus/midi/longo
    if is_moda:
        if any(w in t for w in ["vestido", "saia", "macacão", "conjunto", "blusa", "blazer", "pantalona"]):
            return "moda"

    if any(k in t for k in BRINQ_OK) or any(w in t for w in ["brinquedo", "infantil", "criança", "lego", "boneca"]):
        return "brinquedos"

    return None


def format_msg(o: Offer) -> str:
    emoji = "👗" if o.category == "moda" else "🧸"
    desc = f" ({o.discount_pct:.0f}% OFF)" if o.discount_pct else ""
    de = f"~De R$ {o.original_price:.2f}~ → " if o.original_price and o.original_price > o.price else ""
    return (
        f"{emoji} *OFERTA {o.category.upper()}*{desc}\n"
        f"*{o.title[:120]}*\n\n"
        f"💰 {de}*Por R$ {o.price:.2f}*\n"
        f"🏪 Via {o.source.upper()}\n\n"
        f"👉 {o.url}"
    )
