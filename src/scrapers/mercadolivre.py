"""Busca de ofertas no Mercado Livre via API oficial (OAuth com auto-refresh).

Setup 1x: Redirect URI do app = https://SEU-BOT.onrender.com/callback
→ autoriza no celular → /callback mostra o refresh token → salva no Render.
O bot renova o access_token sozinho (vale 6h).
"""
import time
import httpx
from ..filter import Offer, classify
from ..affiliate import tag_url
from ..config import settings

SEARCHES = [
    "vestido feminino",
    "tenis feminino",
    "bolsa feminina",
    "relogio masculino",
    "brinquedo educativo",
    "tenis infantil",
]

_token = {"access": "", "exp": 0.0, "refresh": ""}

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


def _refresh_token() -> str:
    return _token.get("refresh") or settings.ML_REFRESH_TOKEN


async def refresh_access(client: httpx.AsyncClient) -> bool:
    """Troca refresh_token por access_token novo. Retorna True se ok."""
    if not (settings.ML_CLIENT_ID and settings.ML_CLIENT_SECRET and _refresh_token()):
        return False
    try:
        r = await client.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "refresh_token": _refresh_token(),
        })
        r.raise_for_status()
        j = r.json()
        _token["access"] = j.get("access_token", "")
        _token["exp"] = time.time() + int(j.get("expires_in", 21600)) - 120
        if j.get("refresh_token"):
            _token["refresh"] = j["refresh_token"]
        return bool(_token["access"])
    except Exception:
        return False


def _headers() -> dict:
    h = {"User-Agent": "whatsapp-promos-auto/1.0", "Accept": "application/json"}
    if _token["access"] and _token["exp"] > time.time():
        h["Authorization"] = f"Bearer {_token['access']}"
    return h


async def fetch_ml(query: str, limit: int = 10) -> list[Offer]:
    url = "https://api.mercadolibre.com/sites/MLB/search"
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url, params={"q": query, "limit": limit, "sort": "price_asc"},
                        headers=_headers())
        if r.status_code == 401 and await refresh_access(c):
            r = await c.get(url, params={"q": query, "limit": limit, "sort": "price_asc"},
                            headers=_headers())
        if r.status_code in (401, 403):
            raise RuntimeError("ML sem acesso: confira ML_CLIENT_ID/SECRET/REFRESH_TOKEN")
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
            code=f"ml:{it.get('id', '')}",
        ))
    return out


async def scan_all(min_discount: int = 0, per_query: int = 10) -> list[Offer]:
    if not _token["access"] or _token["exp"] <= time.time():
        async with httpx.AsyncClient(timeout=20) as c:
            if not await refresh_access(c):
                raise RuntimeError("ML: renove o acesso (ML_REFRESH_TOKEN ausente/inválido)")
    found: list[Offer] = []
    errors: list[str] = []
    for q in SEARCHES:
        try:
            found += await fetch_ml(q, per_query)
        except Exception as e:
            errors.append(str(e))
    if min_discount:
        high = [o for o in found if o.discount_pct >= min_discount]
        found = high or found
    seen, uniq = set(), []
    for o in found:
        if o.url not in seen and o.url:
            seen.add(o.url)
            uniq.append(o)
    uniq.sort(key=lambda o: (o.discount_pct, o.price), reverse=True)
    if errors and not uniq:
        raise RuntimeError("; ".join(sorted(set(errors))))
    return uniq
