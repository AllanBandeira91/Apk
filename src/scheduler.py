"""Varredura agendada: Shopee API + ML API + planilha manual -> filtra -> posta."""
import json, pathlib
from .config import settings
from .scrapers.mercadolivre import scan_all as scan_ml
from .scrapers.shopee import scan_all as scan_shopee
from .scrapers.manual import load_manual
from .sender import broadcast

POSTED = pathlib.Path("posted.json")

def load_posted() -> set:
    if POSTED.exists():
        try:
            return set(json.loads(POSTED.read_text()))
        except Exception:
            return set()
    return set()

def save_posted(urls: set):
    POSTED.write_text(json.dumps(sorted(urls)[-500:]))

async def _safe_scan(fn, key: str, out: dict) -> list:
    try:
        return await fn(min_discount=settings.MIN_DISCOUNT_PCT)
    except Exception as e:
        out[key] = str(e)
        return []

def pick_balanced(offers: list, limit: int) -> list:
    """Alterna moda/brinquedos p/ todo scan ter variedade (não só o maior desconto)."""
    buckets: dict[str, list] = {}
    for o in offers:
        buckets.setdefault(o.category or "outros", []).append(o)
    order = [c for c in ("moda", "brinquedos") if c in buckets]
    order += [c for c in buckets if c not in order]
    picked, i = [], 0
    while len(picked) < limit and any(buckets[c] for c in order):
        for c in order:
            if len(picked) >= limit:
                break
            if buckets[c]:
                picked.append(buckets[c].pop(0))
        i += 1
        if i > limit + 10:
            break
    return picked

async def run_scan() -> dict:
    out: dict = {}
    shopee = await _safe_scan(scan_shopee, "shopee_note", out)
    ml = await _safe_scan(scan_ml, "ml_note", out)
    manual = load_manual()
    posted = load_posted()
    # Shopee primeiro (link já com sua comissão), depois ML, depois manual
    # Anti-repetidos: pula por URL e por código do produto (o shortlink muda
    # a cada scan, mas o código do produto é estável) — e envia outro no lugar
    fresh = [o for o in (shopee + ml + manual)
             if o.url not in posted and not (o.code and o.code in posted)]
    # Grupo 1 (Shopee) e Grupo 2 (ML): cada um com seu revezamento moda+kids
    g1 = pick_balanced([o for o in fresh if o.source != "ml"], settings.MAX_OFFERS_PER_SCAN)
    g2 = pick_balanced([o for o in fresh if o.source == "ml"], settings.MAX_OFFERS_PER_SCAN)
    sent1, ok1 = await broadcast(g1, settings.groups)
    sent2, ok2 = await broadcast(g2, settings.ml_groups)
    delivered = ok1 + [o for o in ok2 if o.url not in [d.url for d in ok1]]
    # Só marca como postado o que REALMENTE foi entregue (falha tenta de novo no próximo scan)
    for o in delivered:
        posted.add(o.url)
        if o.code:
            posted.add(o.code)
    save_posted(posted)
    all_offers = g1 + g2
    return {"found_shopee": len(shopee), "found_ml": len(ml), "found_manual": len(manual),
            "new": len(all_offers), "sent": sent1 + sent2,
            "failed": len(all_offers) - len(delivered),
            "titles": [o.title for o in all_offers], **out}
