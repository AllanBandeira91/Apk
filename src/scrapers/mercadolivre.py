"""Busca de ofertas no Mercado Livre via API oficial (precisa ML_ACCESS_TOKEN).

Como tirar o token (grátis, 5 min):
1. https://developers.mercadolivre.com.br → Criar aplicação
2. OAuth: pegue o access_token do seu usuário
3. Cole em ML_ACCESS_TOKEN no .env / Render
Sem token a API retorna 403 (a ML bloqueou busca anônima em 2024).
"""
import httpx
from ..filter import Offer, classify
from ..affiliate import tag_url
from ..config import settings

SEARCHES = [
    "vestido longo evangelica",
    "saia midi evangelica",
    "conjunto saia e blusa feminina",
    "vestido midi godê",
    "lego infantil",
    "boneca barbie",
    "brinquedo educativo criança",
    "hot wheels pista",
]

def _headers() -> dict:
    h = {"User-Agent": "whatsapp-promos-auto/1.0", "Accept": "application/json"}
    if settings.ML_ACCESS_TOKEN:
        h["Authorization"] = f"Bearer {settings.ML_ACCESS_TOKEN}"
    return h

async def fetch_ml(query: str, limit: int = 10) -> list[Offer]:
    url = "https://api.mercadolibre.com/sites/MLB/search"
    async with httpx.AsyncClient(timeout=20, headers=_headers()) as c:
        r = await c.get(url, params={"q": query, "limit": limit, "sort": "price_asc"})
        if r.status_code == 403:
            raise RuntimeError("ML 403: configure ML_ACCESS_TOKEN (busca anônima bloqueada pela ML)")
        r.raise_for_status()
        data = r.json()
    out: list[Offer] = []
    for it in data.get("results", []):
        title = it.get("title", "")
        cat = classify(title)
        if not cat:
            continue
        price = float(it.get("price", 0))
        orig = it.get("original_price")
        out.append(Offer(
            title=title,
            price=price,
            original_price=float(orig) if orig else None,
            url=tag_url(it.get("permalink", ""), "ml"),
            image=(it.get("thumbnail") or "").replace("I.jpg", "O.jpg"),
            source="ml",
            category=cat,
        ))
    return out

async def scan_all(min_discount: int = 0, per_query: int = 10) -> list[Offer]:
    found: list[Offer] = []
    errors: list[str] = []
    for q in SEARCHES:
        try:
            found += await fetch_ml(q, per_query)
        except Exception as e:
            errors.append(str(e))
            continue
    if min_discount:
        found = [o for o in found if o.discount_pct >= min_discount]
    seen, uniq = set(), []
    for o in found:
        if o.url not in seen:
            seen.add(o.url)
            uniq.append(o)
    uniq.sort(key=lambda o: o.discount_pct, reverse=True)
    if errors and not uniq:
        raise RuntimeError("; ".join(sorted(set(errors))))
    return uniq
