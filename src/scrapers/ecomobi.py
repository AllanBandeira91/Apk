"""Busca automática SEM CNPJ via Ecomobi (aceita CPF pessoa física).

Por que: TikTok Shop oficial exige CNPJ/app publicado. A Ecomobi é rede
afiliada que agrega ofertas TikTok Shop + Shopee e gera seu link com
comissão com 1 API key — cadastro grátis com CPF em ~5min.

Como ativar:
  1. Crie conta em https://ecomobi.com (ou app Ecomobi Pass)
  2. Painel -> API / Token -> copie a key
  3. No .env / Render: ECOMOBI_API_KEY=sua_key
  4. Rode /preview — fonte aparece como "ecomobi-live"

Sem a key, levanta RuntimeError e o scheduler cai pro manual (ofertas.csv).
"""
import json
import pathlib

import httpx

from ..config import settings
from ..filter import Offer, classify

BASES = [
    "https://api.ecomobi.com/v1/publishers/offers",
    "https://api.ecomobi.com/api/v1/offers",
    "https://api.ecomobi.com/offers",
]

STATE_FILE = pathlib.Path("ecomobi_state.json")
BATCH = 10

DEFAULT_SEARCHES = [
    "vestido feminino", "tenis feminino", "bolsa feminina",
    "fone bluetooth", "smartwatch", "celular smartphone",
    "air fryer", "lego", "perfume", "mochila",
]


def all_searches() -> list[str]:
    extra: list[str] = []
    for raw in (settings.TIKTOK_SEARCHES, settings.SHOPEE_SEARCHES):
        extra += [s.strip() for s in (raw or "").split(",") if s.strip()]
    base = list(DEFAULT_SEARCHES)
    try:
        from .shopee import all_searches as _sh
        base += [s for s in _sh() if s.lower() not in {b.lower() for b in base}]
    except Exception:
        pass
    base += [e for e in extra if e.lower() not in {b.lower() for b in base}]
    return base


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


def _pick_list(d: dict) -> list:
    for k in ("offers", "data", "products", "items", "result"):
        v = d.get(k)
        if isinstance(v, list) and v:
            return v
        if isinstance(v, dict):
            for kk in ("offers", "list", "items", "products"):
                if isinstance(v.get(kk), list) and v[kk]:
                    return v[kk]
    # varredura genérica
    found: list = []

    def walk(x):
        if isinstance(x, list) and x and isinstance(x[0], dict) and any(
                kk in x[0] for kk in ("title", "name", "product_name", "offer_name")):
            found.append(x)
        elif isinstance(x, dict):
            for vv in x.values():
                walk(vv)
        elif isinstance(x, list):
            for vv in x:
                walk(vv)
    walk(d)
    return found[0] if found else []


def _f(x, default=0.0) -> float:
    try:
        if isinstance(x, dict):
            x = x.get("amount", x.get("value", x.get("price", 0)))
        return float(str(x).replace("R$", "").replace(",", ".").strip() or 0)
    except (TypeError, ValueError):
        return default


def _to_offer(p: dict) -> Offer | None:
    title = str(p.get("title") or p.get("name") or p.get("product_name")
                or p.get("offer_name") or "").strip()
    if not title:
        return None
    cat = classify(title)
    if not cat:
        return None
    url = str(p.get("aff_link") or p.get("affiliate_link") or p.get("offer_link")
              or p.get("link") or p.get("url") or p.get("product_url") or "")
    if not url:
        return None
    price = _f(p.get("sale_price", p.get("price", p.get("salePrice", 0))))
    if price <= 0:
        return None
    orig = _f(p.get("original_price", p.get("market_price", p.get("originalPrice", 0))))
    orig = orig if orig and orig > price else None
    img = p.get("image") or p.get("image_url") or p.get("thumbnail") or ""
    if isinstance(img, list) and img:
        img = img[0]
    if isinstance(img, dict):
        img = img.get("url", "")
    plat = str(p.get("platform") or p.get("merchant") or p.get("source") or "").lower()
    source = "tiktok" if "tiktok" in plat or "tiktok" in url.lower() else "shopee" if "shopee" in plat or "shopee" in url.lower() else (plat or "ecomobi")
    code = f"ecomobi:{p.get('id') or p.get('offer_id') or url}"
    return Offer(title=title, price=price, original_price=orig, url=url,
                 image=str(img or ""), source=source, category=cat, code=code)


async def search(keyword: str, limit: int = 10) -> list[Offer]:
    if not settings.ECOMOBI_API_KEY:
        raise RuntimeError("Ecomobi: configure ECOMOBI_API_KEY (grátis com CPF em ecomobi.com)")
    headers = {"Authorization": f"Bearer {settings.ECOMOBI_API_KEY}",
               "API-Key": settings.ECOMOBI_API_KEY}
    params = {"keyword": keyword, "q": keyword, "search": keyword,
              "limit": limit, "page_size": limit}
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=25) as c:
        for base in BASES:
            try:
                r = await c.get(base, params=params, headers=headers)
                if r.status_code in (404, 405):
                    continue
                r.raise_for_status()
                d = r.json() if "json" in r.headers.get("content-type", "") else {}
                items = _pick_list(d if isinstance(d, dict) else {"offers": d})
                if items:
                    out = []
                    for p in items[:limit]:
                        o = _to_offer(p) if isinstance(p, dict) else None
                        if o:
                            out.append(o)
                    if out:
                        return out
            except Exception as e:
                errors.append(f"{base}: {e}")
                continue
    raise RuntimeError("Ecomobi: sem resposta válida (" + "; ".join(errors[:2]) + "). Confira a key.")


async def scan_all(min_discount: int = 0, per_query: int = 6) -> list[Offer]:
    if not settings.ECOMOBI_ENABLED:
        return []
    found: list[Offer] = []
    errors: list[str] = []
    for q in get_searches():
        try:
            found += await search(q, per_query)
        except Exception as e:
            errors.append(str(e))
            break  # key inválida = nem adianta girar as 10 buscas
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
