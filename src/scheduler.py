"""Varredura agendada: Shopee API + ML API + planilha manual -> filtra -> posta."""
import json
import pathlib
import time
from .config import settings
from .filter import norm_title, titles_match
from .scrapers.mercadolivre import scan_all as scan_ml
from .scrapers.shopee import scan_all as scan_shopee
from .scrapers.manual import load_manual
from .sender import broadcast, group_history

POSTED = pathlib.Path("posted.json")
HISTORY = pathlib.Path("sent_history.json")  # chave(url/código) -> título normalizado

def load_posted() -> set:
    if POSTED.exists():
        try:
            return set(json.loads(POSTED.read_text()))
        except Exception:
            return set()
    return set()

def save_posted(urls: set):
    POSTED.write_text(json.dumps(sorted(urls)[-500:]))

def load_history() -> dict:
    if HISTORY.exists():
        try:
            return json.loads(HISTORY.read_text())
        except Exception:
            return {}
    return {}

def save_history(h: dict):
    items = sorted(h.items(), key=lambda kv: kv[1].get("ts", 0) if isinstance(kv[1], dict) else 0)[-2000:]
    HISTORY.write_text(json.dumps(dict(items), ensure_ascii=False))

async def _safe_scan(fn, key: str, out: dict) -> list:
    try:
        return await fn(min_discount=settings.MIN_DISCOUNT_PCT)
    except Exception as e:
        out[key] = str(e)
        return []

def pick_balanced(offers: list, limit: int) -> list:
    """Alterna entre as seções (moda/calcados/acessorios/kids/bebe),
    girando a seção inicial a cada scan p/ todas aparecerem."""
    buckets: dict[str, list] = {}
    for o in offers:
        buckets.setdefault(o.category or "outros", []).append(o)
    cats = sorted(buckets.keys())
    try:
        st = json.loads(pathlib.Path("scan_state.json").read_text())
    except Exception:
        st = {}
    start = int(st.get("pick", 0)) % max(len(cats), 1)
    order = cats[start:] + cats[:start]
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
    try:
        st["pick"] = int(st.get("pick", 0)) + 1
        pathlib.Path("scan_state.json").write_text(json.dumps(st))
    except Exception:
        pass
    return picked

async def run_scan() -> dict:
    out: dict = {}
    shopee = await _safe_scan(scan_shopee, "shopee_note", out)
    ml = await _safe_scan(scan_ml, "ml_note", out)
    manual = load_manual()
    posted = load_posted()
    history = load_history()
    # Checa o histórico REAL dos grupos antes de enviar (links + títulos)
    group_urls: set = set()
    group_titles: list = []
    for jid in settings.groups + settings.ml_groups:
        try:
            u, t = await group_history(jid)
            group_urls |= u
            group_titles += [norm_title(x) for x in t]
        except Exception:
            continue
    known_titles = [v["t"] if isinstance(v, dict) else v for v in history.values()] + group_titles

    def is_dupe(o) -> bool:
        # 1) link ou código já enviado
        if o.url in posted or o.url in group_urls or (o.code and o.code in posted):
            return True
        # 2) título igual ou quase igual a algo já postado no grupo
        nt = norm_title(o.title)
        return any(titles_match(nt, k) for k in known_titles)

    candidates = list(shopee + ml + manual)
    fresh = [o for o in candidates if not is_dupe(o)]
    skipped = len(candidates) - len(fresh)
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
        history[o.code or o.url] = {"t": norm_title(o.title), "ts": int(time.time())}
    save_posted(posted)
    save_history(history)
    all_offers = g1 + g2
    return {"found_shopee": len(shopee), "found_ml": len(ml), "found_manual": len(manual),
            "new": len(all_offers), "sent": sent1 + sent2,
            "failed": len(all_offers) - len(delivered),
            "skipped_dupes": skipped,
            "titles": [o.title for o in all_offers], **out}
