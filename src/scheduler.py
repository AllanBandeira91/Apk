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

async def run_scan() -> dict:
    out: dict = {}
    shopee = await _safe_scan(scan_shopee, "shopee_note", out)
    ml = await _safe_scan(scan_ml, "ml_note", out)
    manual = load_manual()
    posted = load_posted()
    # Shopee primeiro (link já com sua comissão), depois ML, depois manual
    all_offers = [o for o in (shopee + ml + manual) if o.url not in posted][: settings.MAX_OFFERS_PER_SCAN]
    sent = await broadcast(all_offers)
    posted.update(o.url for o in all_offers)
    save_posted(posted)
    return {"found_shopee": len(shopee), "found_ml": len(ml), "found_manual": len(manual),
            "new": len(all_offers), "sent": sent,
            "titles": [o.title for o in all_offers], **out}
