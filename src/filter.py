"""Modelo + filtro: moda geral (sem roupa quase-pelada) + bebê/brinquedos."""
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

@dataclass
class Offer:
    title: str
    price: float
    original_price: float | None
    url: str
    image: str
    source: str  # ml | shopee | amazon | aliexpress
    category: str = ""  # moda | brinquedos
    code: str = ""  # identidade estável do produto (ex: shopee:123). Não muda entre scans.

    @property
    def discount_pct(self) -> float:
        if not self.original_price or self.original_price <= self.price or self.original_price <= 0:
            return 0.0
        return round((1 - self.price / self.original_price) * 100, 1)

# Roupa/quase-pelada: sempre bloqueia
REVEAL_BLOCK = [
    "biquini", "biquíni", "maiô", "sunga",
    "lingerie", "calcinha", "sutiã", "sutia", "espartilho", "cinta liga",
    "transparente", "decote profundo", "decotad", "fenda alta",
    "fio dental", "body cavado", "tomara que caia", "fantasia sexy",
]

# Moda geral: roupa, calçado, joia/bijuteria, relógio, bolsa
MODA_OK = [
    "vestido", "saia", "blusa", "camisa", "camiseta", "regata", "cropped",
    "calça", "calca", "short", "bermuda", "legging", "jaqueta", "casaco",
    "moletom", "conjunto", "macacão", "macacao", "jardineira", "pijama",
    "tenis", "tênis", "sapato", "sapatilha", "sandalia", "sandália",
    "chinelo", "bota", "salto", "mocassim", "chuteira", "sapatênis", "sapatenis",
    "brinco", "anel", "colar", "pulseira", "tornozeleira", "relogio", "relógio",
    "smartwatch", "bolsa", "mochila", "carteira", "oculos", "óculos",
    "cinto", "chapeu", "chapéu", "bone", "boné", "bijuteria", "folhead",
    "prata 925", "semijoia", "semijoias", "touca", "gorro", "meia", "tiara",
]

# Bebê
BEBE_OK = [
    "fralda", "mamadeira", "chupeta", "mordedor", "babador",
    "carrinho de bebe", "carrinho de bebê", "berco", "berço",
    "banheira", "kit berco", "kit berço", "trocador",
    "bolsa maternidade", "kit higiene bebe", "kit higiene bebê",
    "roupa bebe", "roupa bebê", "body bebe", "body bebê",
    "mamadeira", "esterilizador", "bomba tira-leite", "cadeirinha",
    "bebê conforto", "bebe conforto", "andador bebe", "chocalho",
    "sapatinho", "sandalhinha", "cueiro", "pagao", "pagão",
]

# Brinquedos criança
BRINQ_OK = [
    "lego", "barbie", "carrinho", "boneca", "boneco",
    "quebra-cabeça", "quebra cabeca", "jogo educativo", "brinquedo educativo",
    "massinha", "play doh", "hot wheels", "pelucia", "pelúcia",
    "patinete", "blocos de montar", "dinossauro brinquedo",
    "cozinha infantil", "baby alive", "nerf", "pista",
    "bicicleta infantil", "bola", "piscina infantil", "barraca infantil",
]

KID_CTX = ["infantil", "criança", "crianca", "kids", "menina", "menino"]


def _has(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def classify(title: str) -> str | None:
    """Retorna 'moda' | 'brinquedos' | None (rejeitado)."""
    t = title.lower()

    if _has(t, REVEAL_BLOCK):
        return None
    if _has(t, BEBE_OK) or re.search(r"\bbeb[eê]\b|\brec[eé]m-nascido\b", t):
        return "brinquedos"  # \b evita falso positivo tipo "bebedouro"
    if _has(t, BRINQ_OK):
        return "brinquedos"
    if _has(t, MODA_OK):
        # tênis/vestido infantil vai pra prateleira kids
        if _has(t, KID_CTX):
            return "brinquedos"
        return "moda"
    if _has(t, KID_CTX) and _has(t, ["brinquedo", "jogo", "diversao", "diversão"]):
        return "brinquedos"
    return None


def norm_title(t: str) -> str:
    """Normaliza p/ comparar: sem acento, minúsculo, só letras/números."""
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def titles_match(a: str, b: str, thresh: float = 0.88) -> bool:
    """True se títulos (já normalizados) são o mesmo item ou quase."""
    if not a or not b or a == b:
        return bool(a and a == b)
    if len(a) < 8 or len(b) < 8:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if len(short) >= 10 and short in long and len(short) / len(long) > 0.6:
        return True
    return SequenceMatcher(None, a, b).ratio() >= thresh


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
