"""Varredura agendada: Shopee API + TikTok Shop API + planilha manual -> filtra -> posta."""
import json
import pathlib
import re
import time
from datetime import datetime
from .config import settings
from .filter import norm_title, titles_match
from .scrapers.shopee import scan_all as scan_shopee
from .scrapers.tiktok import scan_all as scan_tiktok
from .scrapers.ecomobi import scan_all as scan_ecomobi
from .scrapers.manual import load_manual
from .sender import broadcast, group_history, send_plain_text

POSTED = pathlib.Path("posted.json")
HISTORY = pathlib.Path("sent_history.json")  # chave(url/código) -> título normalizado

def load_posted() -> list:
    """LRU por inserção: só o entregue RECENTEMENTE bloqueia (antigos podem voltar)."""
    if POSTED.exists():
        try:
            d = json.loads(POSTED.read_text())
            return list(d) if isinstance(d, list) else []
        except Exception:
            return []
    return []

def save_posted(urls: list):
    # dedup preservando ordem (mais recentes no fim) e descartando os mais antigos
    POSTED.write_text(json.dumps(list(dict.fromkeys(urls))[-1000:]))

def load_history() -> dict:
    if HISTORY.exists():
        try:
            return json.loads(HISTORY.read_text())
        except Exception:
            return {}
    return {}

def save_history(h: dict):
    items = sorted(h.items(), key=lambda kv: kv[1].get("ts", 0) if isinstance(kv[1], dict) else 0)[-5000:]
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
                cand = buckets[c].pop(0)
                # os 2 do mesmo scan não podem ser parecidos entre si
                nt = norm_title(cand.title)
                if any(titles_match(nt, norm_title(p.title)) for p in picked):
                    continue
                picked.append(cand)
        i += 1
        if i > limit + 10:
            break
    try:
        st["pick"] = int(st.get("pick", 0)) + 1
        pathlib.Path("scan_state.json").write_text(json.dumps(st))
    except Exception:
        pass
    return picked

# Prioridade de Natal: titulos com esses termos ganham vaga garantida no scan
# (cuidado: "pre natal" de gestante NAO e natal — ignoramos esse caso)
_NATAL_RE = re.compile(r"(?<!pre )\bnatal\b|\bnoel\b|\bpinheiro\b")


def is_natal(o) -> bool:
    return bool(_NATAL_RE.search(norm_title(o.title)))


# ---- Janela de postagem: promoções só das 09:00 às 00:00 (madrugada silenciosa)
POST_START_HOUR = 9
POST_END_HOUR = 24  # 00:00 (exclusivo): horas 9..23 postam; 0..8 em silêncio


def dentro_da_janela(agora: datetime | None = None) -> bool:
    h = (agora or datetime.now()).hour
    return POST_START_HOUR <= h < POST_END_HOUR


AVISO_ABERTURA = (
    "⏰ *ATENÇÃO, PESSOAL!*\n\n"
    "As promoções se iniciam em *10 MINUTOS*! 🛒\n"
    "Deixa o dedinho pronto que vem oferta boa! 🔥"
)

AVISO_FECHAMENTO = (
    "🌙 *PROMOÇÕES ENCERRADAS POR HOJE!*\n\n"
    "Obrigado a quem aproveitou as ofertas! 💛\n"
    "Voltamos amanhã às *09:00* com promoções novas. Até lá! 💤🎁"
)


async def announce_open():
    n = await send_plain_text(AVISO_ABERTURA)
    print(f"[aviso] abertura enviada ({n} grupo(s))", flush=True)


async def announce_close():
    n = await send_plain_text(AVISO_FECHAMENTO)
    print(f"[aviso] fechamento enviado ({n} grupo(s))", flush=True)


async def run_scan(force: bool = False) -> dict:
    agora = datetime.now()
    if not force and not dentro_da_janela(agora):
        return {"paused": True, "hora": agora.strftime("%H:%M"),
                "info": "fora da janela (09:00-00:00): nada foi enviado"}
    out: dict = {}
    shopee = await _safe_scan(scan_shopee, "shopee_note", out)
    tiktok = await _safe_scan(scan_tiktok, "tiktok_note", out)
    ecomobi = await _safe_scan(scan_ecomobi, "ecomobi_note", out)
    manual = load_manual()
    posted = load_posted()
    history = load_history()
    # Checa o histórico REAL do grupo antes de enviar (links + títulos)
    group_urls: set = set()
    group_titles: list = []
    for jid in settings.groups:
        try:
            u, t = await group_history(jid)
            group_urls |= u
            group_titles += [norm_title(x) for x in t]
        except Exception:
            continue
    # Reciclagem: bloqueia só o que foi enviado nos últimos REPOST_AFTER_DAYS dias;
    # depois disso a oferta PODE VOLTAR — sem isso o grupo "seca", pois a Shopee
    # retorna os mesmos itens nas buscas e tudo vira "duplicado".
    recorte = time.time() - settings.REPOST_AFTER_DAYS * 86400
    known_titles = ([v["t"] for v in history.values()
                     if isinstance(v, dict) and v.get("ts", 0) > recorte]
                    + group_titles)

    def is_dupe(o) -> bool:
        # 1) enviado há pouco? (histórico local com data — recicla após a janela)
        ev = history.get(o.code or o.url)
        if isinstance(ev, dict) and ev.get("ts", 0) > recorte:
            return True
        # 2) entregue recentemente (LRU) ou link visto nas últimas msgs do grupo
        if o.url in posted or (o.code and o.code in posted) or o.url in group_urls:
            return True
        # 3) título igual ou quase igual a algo recente
        nt = norm_title(o.title)
        return any(titles_match(nt, k) for k in known_titles)

    candidates = list(shopee + tiktok + ecomobi + manual)
    fresh = [o for o in candidates if not is_dupe(o)]
    skipped = len(candidates) - len(fresh)
    # Prioridade de Natal: garante 1 item natalino por scan (se houver)
    natal = [o for o in fresh if is_natal(o)]
    restante = [o for o in fresh if not is_natal(o)]
    all_offers: list = []
    if natal:
        all_offers.append(natal.pop(0))
        nt = norm_title(all_offers[0].title)
        restante = [o for o in restante if not titles_match(nt, norm_title(o.title))]
    all_offers += pick_balanced(restante, settings.MAX_OFFERS_PER_SCAN - len(all_offers))
    sent, delivered = await broadcast(all_offers, settings.groups)
    # Só marca como postado o que REALMENTE foi entregue (falha tenta de novo no próximo scan)
    for o in delivered:
        posted.append(o.url)
        if o.code:
            posted.append(o.code)
        history[o.code or o.url] = {"t": norm_title(o.title), "ts": int(time.time())}
    save_posted(posted)
    save_history(history)
    try:
        pathlib.Path("last_run.json").write_text(json.dumps(
            {"ts": int(time.time()), "sent": sent}))
    except Exception:
        pass
    res = {"found_shopee": len(shopee), "found_tiktok": len(tiktok), "found_ecomobi": len(ecomobi), "found_manual": len(manual),
           "new": len(all_offers), "sent": sent,
           "failed": len(all_offers) - len(delivered),
           "skipped_dupes": skipped,
           "titles": [o.title for o in all_offers], **out}
    # log detalhado: de onde vieram, quantas novas, quantas enviadas, quantas falharam
    print(f"[scan] {agora:%d/%m %H:%M} | shopee={len(shopee)} tiktok={len(tiktok)} ecomobi={len(ecomobi)} manual={len(manual)}"
          f" | novas={res['new']} enviadas={sent} falhas={res['failed']} dupes_ignoradas={skipped}",
          flush=True)
    if res["failed"]:
        print(f"[scan]   falharam: {[o.title[:40] for o in all_offers if o not in delivered]}", flush=True)
    return res
