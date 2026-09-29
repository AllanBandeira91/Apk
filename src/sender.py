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

async def broadcast(offers: list[Offer]) -> int:
    sent = 0
    for g in settings.groups:
        for o in offers:
            if await send_to_group(g, o):
                sent += 1
    return sent
