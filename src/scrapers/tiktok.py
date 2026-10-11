"""Busca ofertas na TikTok Shop via Affiliate Open API oficial.

Docs: https://partner.tiktokshop.com/docv2 (seção Affiliate).
Requer no .env / Render:
  TIKTOK_APP_KEY=<seu app key do Partner Center>
  TIKTOK_APP_SECRET=<seu app secret do Partner Center>
  TIKTOK_ACCESS_TOKEN=<token da loja/criador que autorizou o app>
  TIKTOK_SHOP_CIPHER=<opcional, alguns endpoints pedem>

Como pegar o ACCESS_TOKEN (1x só):
  1. Partner Center -> seu app -> Authorize / Generate token da loja de teste
     ou complete o OAuth da loja/criador e copie o access_token.
  2. Cole em TIKTOK_ACCESS_TOKEN no .env / Render. Sem ele a API
     retorna erro de auth — nesse caso o bot usa o fallback manual
     (ofertas.csv com links vt.tiktok.com da sua vitrine).

Assinatura: HMAC-SHA256(secret, secret + path + params_ordenados + body + secret).
"""
import hashlib
import hmac
import json
import pathlib
import time

import httpx

from ..config import settings
from ..filter import Offer, classify

BASE = "https://open-api.tiktokglobalshop.com"

STATE_FILE = pathlib.Path("tiktok_state.json")
BATCH = 10

DEFAULT_SEARCHES = [
    "vestido feminino", "tenis feminino", "bolsa feminina",
    "relogio", "fone bluetooth", "smartwatch",
    "air fryer", "liquidificador", "lego", "boneca",
    "celular smartphone", "notebook", "cadeira gamer",
    "perfume", "maquiagem", "skincare",
    "whey protein", "bicicleta", "mochila", "ventilador",
]


def all_searches() -> list[str]:
    extra = [s.strip() for s in (settings.TIKTOK_SEARCHES or "").split(",") if s.strip()]
    base = list(DEFAULT_SEARCHES)
    try:  # reaproveita também as buscas da Shopee (qualquer categoria)
        from .shopee import all_searches as _sh
        base += [s for s in _sh() if s.lower() not in {b.lower() for b in base}]
    except Exception:
        pass
    return base + [e for e in extra if e.lower() not in {b.lower() for b in base}]


def get_searches() -> list[str]:
    pool = all_searches()
    try:
        st = json.loads(STATE_FILE.read_text())
        off = int(st.get("offset", 0)) % len(pool)
    except Exception:
        st, off = {}, 0
    batch = [pool[(off + i) % len(pool)] for i in range(BATCH)]
    try:
        st["offset"] = (off + BATCH) % len(pool)
        STATE_FILE.write_text(json.dumps(st))
    except Exception:
        pass
    return batch


def _sign(path: str, params: dict, body_str: str = "") -> str:
    secret = settings.TIKTOK_APP_SECRET or ""
    filt = {k: v for k, v in params.items() if k not in ("sign", "access_token")}
    concat = "".join(f"{k}{v}" for k, v in sorted(filt.items()))
    base_str = f"{secret}{path}{concat}{body_str}{secret}"
    return hmac.new(secret.encode(), base_str.encode(), hashlib.sha256).hexdigest()


def _params(extra: dict | None = None) -> dict:
    p = {"app_key": settings.TIKTOK_APP_KEY or "", "timestamp": str(int(time.time()))}
    if extra:
        p.update(extra)
    return p


async def _call(client: httpx.AsyncClient, method: str, path: str,
               query_extra: dict | None = None, body: dict | None = None) -> dict:
    params = _params(query_extra)
    body_str = json.dumps(body, separators=(",", ":")) if body is not None else ""
    params["sign"] = _sign(path, params, body_str)
    url = BASE + path
    # access_token vai como query param mas NÃO entra no sign
    if settings.TIKTOK_ACCESS_TOKEN:
        params["access_token"] = settings.TIKTOK_ACCESS_TOKEN
    if settings.TIKTOK_SHOP_CIPHER:
        params["shop_cipher"] = settings.TIKTOK_SHOP_CIPHER
    if method == "GET":
        r = await client.get(url, params=params)
    else:
        r = await client.post(url, params=params,
                              content=body_str or None,
                              headers={"Content-Type": "application/json"})
    r.raise_for_status()
    return r.json()


def _walk_lists(x, out: list):
    if isinstance(x, list):
        # lista de dicts com cara de produto?
        if x and isinstance(x[0], dict) and any(
                k in x[0] for k in ("product_id", "productId", "product_name",
                                   "productName", "title", "name")):
            out.append(x)
        for v in x:
            _walk_lists(v, out)
    elif isinstance(x, dict):
        for v in x.values():
            _walk_lists(v, out)


def _num(x, default=0.0) -> float:
    try:
        if isinstance(x, dict):  # {"amount": "99.90", "currency": "BRL"}
            x = x.get("amount", x.get("value", x.get("price", 0)))
        return float(str(x).replace("R$", "").replace(",", ".").strip() or 0)
    except (TypeError, ValueError):
        return default


def _to_offer(p: dict, promo_link: str = "") -> Offer | None:
    title = str(p.get("product_name") or p.get("productName")
                or p.get("title") or p.get("name") or "").strip()
    if not title:
        return None
    cat = classify(title)
    if not cat:
        return None  # bloqueado (adulto/quase-pelado)
    pid = str(p.get("product_id") or p.get("productId") or p.get("id") or "")
    price = _num(p.get("sale_price", p.get("salePrice", p.get("price", 0))))
    if price <= 0:
        # tenta price antigo/novo: alguns payloads trazem "price": {"sale_price":..}
        price = _num(p.get("min_price", p.get("minPrice", 0)))
    if price <= 0:
        return None
    orig = _num(p.get("original_price", p.get("originalPrice",
                p.get("market_price", p.get("marketPrice", 0)))))
    orig = orig if orig and orig > price else None
    url = (promo_link
           or str(p.get("share_link") or p.get("shareLink")
                  or p.get("product_url") or p.get("productUrl") or ""))
    if not url and pid:
        url = f"https://shop.tiktok.com/product/{pid}"
    img = p.get("main_image") or p.get("mainImage") or p.get("image_url") or p.get("imageUrl") or ""
    if isinstance(img, dict):
        img = img.get("url", "")
    if isinstance(img, list) and img:
        img = img[0] if isinstance(img[0], str) else img[0].get("url", "")
    return Offer(title=title, price=price, original_price=orig,
                 url=url, image=str(img or ""), source="tiktok",
                 category=cat, code=f"tiktok:{pid}" if pid else "")


async def _promo_link(client: httpx.AsyncClient, product_id: str, fallback: str) -> str:
    """Gera link de afiliado com sua comissão. Cai pro link original se falhar."""
    if not product_id:
        return fallback
    for path, body in (
        ("/affiliate/open_api/v2/link/generate", {"product_id": product_id}),
        ("/affiliate/open_api/v1/link/generate", {"product_id": product_id}),
    ):
        try:
            d = await _call(client, "POST", path, body=body)
            data = d.get("data") or {}
            link = data.get("share_link") or data.get("shareLink") or data.get("short_link") or ""
            if link:
                return link
        except Exception:
            continue
    return fallback


async def search(keyword: str, limit: int = 10) -> list[Offer]:
    if not settings.TIKTOK_APP_KEY or not settings.TIKTOK_APP_SECRET:
        raise RuntimeError("TikTok: configure TIKTOK_APP_KEY e TIKTOK_APP_SECRET")
    if not settings.TIKTOK_ACCESS_TOKEN:
        raise RuntimeError("TikTok: configure TIKTOK_ACCESS_TOKEN (autorize o app 1x no Partner Center)")
    out: list[Offer] = []
    async with httpx.AsyncClient(timeout=25) as c:
        raw: dict | None = None
        errors: list[str] = []
        attempts = (
            ("POST", "/affiliate/open_api/v2/product/search",
             {"keyword": keyword, "page_size": limit, "page_no": 1}),
            ("POST", "/affiliate/open_api/v1/product/search",
             {"keyword": keyword, "page_size": limit, "page_no": 1}),
            ("GET", "/affiliate/open_api/v1/product/search",
             {"keyword": keyword, "page_size": str(limit)}),
        )
        for method, path, payload in attempts:
            try:
                if method == "GET":
                    raw = await _call(c, "GET", path, query_extra=payload)
                else:
                    raw = await _call(c, "POST", path, body=payload)
                if (raw.get("code") not in (None, 0) and raw.get("code") != 0):
                    errors.append(f"{path}: {raw.get('message', raw.get('code'))}")
                    raw = None
                    continue
                break
            except Exception as e:
                errors.append(f"{path}: {e}")
                raw = None
        if raw is None:
            raise RuntimeError("; ".join(errors) or "TikTok: sem resposta da API")
        buckets: list = []
        _walk_lists(raw, buckets)
        products: list[dict] = buckets[0] if buckets else []
        for p in products[:limit]:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("product_id") or p.get("productId") or p.get("id") or "")
            tmp = _to_offer(p)
            if not tmp:
                continue
            tmp.url = await _promo_link(c, pid, tmp.url)
            out.append(tmp)
    return out


async def scan_all(min_discount: int = 0, per_query: int = 6) -> list[Offer]:
    if not settings.TIKTOK_ENABLED:
        return []
    found: list[Offer] = []
    errors: list[str] = []
    for q in get_searches():
        try:
            found += await search(q, per_query)
        except Exception as e:
            errors.append(str(e))
    if min_discount:
        high = [o for o in found if o.discount_pct >= min_discount]
        found = high or found
    seen, uniq = set(), []
    for o in found:
        key = o.url or o.code
        if key and key not in seen:
            seen.add(key)
            uniq.append(o)
    uniq.sort(key=lambda o: (o.discount_pct, o.price), reverse=True)
    if errors and not uniq:
        raise RuntimeError("; ".join(sorted(set(errors))))
    return uniq
