"""Envio via Evolution API (padrão BR para bot WhatsApp)."""
import httpx
from .config import settings
from .filter import Offer, format_msg

def evolution_headers() -> dict:
    return {"apikey": settings.EVOLUTION_APIKEY, "Content-Type": "application/json"}

async def send_to_group(group_jid: str, offer: Offer) -> bool:
    """Tenta enviar imagem+legenda; cai pra texto se falhar."""
    if not settings.EVOLUTION_API_URL:
        print(f"[DRY] {offer.category} | {offer.title[:60]} -> {group_jid}")
        return False
    base = settings.EVOLUTION_API_URL.rstrip("/")
    inst = settings.EVOLUTION_INSTANCE
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            if offer.image:
                r = await c.post(
                    f"{base}/message/sendMedia/{inst}",
                    headers=evolution_headers(),
                    json={"number": group_jid, "mediatype": "image",
                          "media": offer.image, "caption": format_msg(offer)},
                )
                if r.status_code < 300:
                    return True
            r = await c.post(
                f"{base}/message/sendText/{inst}",
                headers=evolution_headers(),
                json={"number": group_jid, "text": format_msg(offer)},
            )
            return r.status_code < 300
        except Exception as e:
            print("send fail:", e)
            return False

async def group_history(jid: str, limit: int = 100) -> tuple[set, list]:
    """Lê msgs recentes do grupo (best-effort): retorna (urls, títulos)."""
    import re as _re
    if not settings.EVOLUTION_API_URL:
        return set(), []
    base = settings.EVOLUTION_API_URL.rstrip("/")
    urls, titles = set(), []
    async with httpx.AsyncClient(timeout=30) as c:
        try:
            r = await c.post(
                f"{base}/chat/findMessages/{settings.EVOLUTION_INSTANCE}",
                headers=evolution_headers(),
                json={"where": {"key": {"remoteJid": jid}}, "limit": limit},
            )
            if r.status_code >= 300:
                return set(), []
            data = r.json()
        except Exception:
            return set(), []
    found: list[str] = []

    def walk(x):
        if isinstance(x, str):
            found.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(data)
    for s in found:
        urls.update(_re.findall(r"https?://\S+", s))
        titles += [t.strip() for t in _re.findall(r"\*(.+?)\*", s) if len(t.strip()) > 10]
    return urls, titles


async def broadcast(offers: list[Offer], groups: list[str] | None = None) -> tuple[int, list[Offer]]:
    """Retorna (nº msgs enviadas, ofertas entregues em ≥1 grupo)."""
    delivered: list[Offer] = []
    sent = 0
    for g in (groups if groups is not None else settings.groups):
        for o in offers:
            if await send_to_group(g, o):
                sent += 1
                if all(o.code != d.code or not o.code for d in delivered) and o.url not in [d.url for d in delivered]:
                    delivered.append(o)
    return sent, delivered
