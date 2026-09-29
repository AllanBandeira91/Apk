"""Busca ofertas na Shopee via Affiliate Open API (GraphQL oficial).

Endpoint BR: https://open-api.affiliate.shopee.com.br/graphql
Auth: SHA256(appId + timestamp + payload + secret) no header Authorization.
Requer SHOPEE_APPID + SHOPEE_SECRET no .env / Render (nunca commitar).
"""
import hashlib
import json
import pathlib
import time
import httpx
from ..filter import Offer, classify
from ..config import settings

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"

SEARCHES = [
    "vestido feminino",
    "blusa feminina",
    "tenis feminino",
    "sandalia feminina",
    "bolsa feminina",
    "kit brinco folheado",
    "relogio feminino",
    "roupa bebe",
    "sapatinho bebe",
    "relogio infantil",
    "kit higiene bebe",
    "tenis infantil",
    "lego",
    "boneca",
    "camisa masculina",
    "bermuda masculina",
    "tenis masculino",
    "bone masculino",
]

STATE_FILE = pathlib.Path("scan_state.json")
BATCH = 8  # buscas por scan (rodízio: cobre tudo ao longo do dia sem estourar timeout)


def get_searches() -> list[str]:
    """Rodízio das buscas: cada scan pega um lote diferente."""
    try:
        off = json.loads(STATE_FILE.read_text()).get("offset", 0) % len(SEARCHES)
    except Exception:
        off = 0
    batch = [SEARCHES[(off + i) % len(SEARCHES)] for i in range(BATCH)]
    try:
        STATE_FILE.write_text(json.dumps({"offset": (off + BATCH) % len(SEARCHES)}))
    except Exception:
        pass
    return batch

QUERY = """
query($keyword: String, $sortType: Int, $page: Int, $limit: Int) {
  productOfferV2(keyword: $keyword, sortType: $sortType, page: $page, limit: $limit) {
    nodes {
      productName itemId shopId shopName
      price priceMin priceMax priceDiscountRate
      sales ratingStar imageUrl productLink offerLink
      commission commissionRate sellerCommissionRate shopeeCommissionRate
      periodStartTime periodEndTime
    }
    pageInfo { page limit hasNextPage }
  }
}
"""

SHORTLINK_MUT = """
mutation($url: String!) {
  generateShortLink(input: {originUrl: $url, subIds: ["whatsapp", "grupo-promos"]}) {
    shortLink
  }
}
"""


def _auth_headers(payload: str) -> dict:
    ts = str(int(time.time()))
    raw = f"{settings.SHOPEE_APPID}{ts}{payload}{settings.SHOPEE_SECRET}"
    sig = hashlib.sha256(raw.encode()).hexdigest()
    return {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={settings.SHOPEE_APPID}, Timestamp={ts}, Signature={sig}",
    }


async def _gql(client: httpx.AsyncClient, query: str, variables: dict) -> dict:
    import json as _json
    payload = _json.dumps({"query": query, "variables": variables}, separators=(",", ":"))
    r = await client.post(ENDPOINT, content=payload, headers=_auth_headers(payload))
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        err = data["errors"][0]
        code = (err.get("extensions") or {}).get("code", "?")
        raise RuntimeError(f"Shopee erro {code}: {err.get('message')}")
    return data["data"]


async def short_link(client: httpx.AsyncClient, url: str) -> str:
    """Converte em link curto de afiliado (com sua comissão). Cai pro original se falhar."""
    try:
        data = await _gql(client, SHORTLINK_MUT, {"url": url})
        return data["generateShortLink"]["shortLink"] or url
    except Exception:
        return url


def _to_offer(n: dict, url: str) -> Offer | None:
    title = (n.get("productName") or "").strip()
    if not title:
        return None
    cat = classify(title)
    if not cat:
        return None
    try:
        price = float(n.get("priceMin") or n.get("price") or 0)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None
    rate = n.get("priceDiscountRate") or 0
    orig = round(price / (1 - rate / 100), 2) if rate and 0 < rate < 90 else None
    return Offer(
        title=title, price=price, original_price=orig,
        url=url, image=n.get("imageUrl") or "",
        source="shopee", category=cat,
        code=f"shopee:{n.get('itemId') or n.get('shopId')}",
    )


async def search(keyword: str, limit: int = 10, sort_type: int = 2) -> list[Offer]:
    if not settings.SHOPEE_APPID or not settings.SHOPEE_SECRET:
        raise RuntimeError("Shopee: configure SHOPEE_APPID e SHOPEE_SECRET")
    out: list[Offer] = []
    async with httpx.AsyncClient(timeout=25) as c:
        data = await _gql(c, QUERY, {"keyword": keyword, "sortType": sort_type, "page": 1, "limit": limit})
        nodes = (data.get("productOfferV2") or {}).get("nodes") or []
        for n in nodes:
            base = n.get("offerLink") or n.get("productLink") or ""
            if not base:
                continue
            o = _to_offer(n, base)
            if o:
                o.url = await short_link(c, base)
                out.append(o)
    return out


async def scan_all(min_discount: int = 0, per_query: int = 5) -> list[Offer]:
    found: list[Offer] = []
    errors: list[str] = []
    for q in get_searches():
        try:
            found += await search(q, per_query)
        except Exception as e:
            errors.append(str(e))
    if min_discount:
        high = [o for o in found if o.discount_pct >= min_discount]
        found = high or found  # se nada bate o mínimo, mantém p/ não zerar o dia
    seen, uniq = set(), []
    for o in found:
        if o.url not in seen and o.url:
            seen.add(o.url)
            uniq.append(o)
    uniq.sort(key=lambda o: (o.discount_pct, o.price), reverse=True)
    if errors and not uniq:
        raise RuntimeError("; ".join(sorted(set(errors))))
    return uniq
