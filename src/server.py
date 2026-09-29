"""Painel + API p/ Render. Rota /scan dispara varredura manual."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .config import settings
from .scheduler import run_scan

sched = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    sched.add_job(run_scan, "interval", minutes=settings.SCAN_INTERVAL_MIN, id="scan")
    sched.start()
    yield
    sched.shutdown()

app = FastAPI(lifespan=lifespan)

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home():
    return f"""
    <h2>🤖 Promo Bot — Moda Crente + Brinquedos</h2>
    <p>Grupo Shopee: {len(settings.groups)} | Grupo ML: {len(settings.ml_groups)} | Intervalo: {settings.SCAN_INTERVAL_MIN}min</p>
    <p>Evolution: {'✅ configurada' if settings.EVOLUTION_API_URL else '❌ configure EVOLUTION_API_URL'}</p>
    <a href="/scan"><button>🔍 Buscar e postar agora</button></a> |
    <a href="/preview"><button>👀 Ver prévias sem postar</button></a>
    <p>Como conectar: suba a Evolution API, crie instance '{settings.EVOLUTION_INSTANCE}',
    leia o QR, crie o grupo e cole o JID em TARGET_GROUPS.</p>
    """

@app.get("/scan")
async def scan():
    return await run_scan()

@app.get("/callback")
async def callback(code: str = ""):
    """Recebe o ?code= da ML, troca por tokens e mostra o refresh p/ salvar 1x."""
    import httpx
    if not code:
        return {"error": "sem ?code= — abra o link de autorização primeiro"}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post("https://api.mercadolibre.com/oauth/token", data={
                "grant_type": "authorization_code",
                "client_id": settings.ML_CLIENT_ID,
                "client_secret": settings.ML_CLIENT_SECRET,
                "code": code,
                "redirect_uri": "https://apk-7s44.onrender.com/callback",
            })
            r.raise_for_status()
            j = r.json()
    except Exception as e:
        return {"error": f"troca falhou: {str(e)[:200]} — confira ML_CLIENT_ID/SECRET no Render"}
    rt = j.get("refresh_token", "")
    return HTMLResponse(
        f"<h2>✅ Conectado ao Mercado Livre!</h2>"
        f"<p>Copie e salve no Render (ML_REFRESH_TOKEN):</p>"
        f"<p style='font-size:20px;background:#eee;padding:12px;word-break:break-all'>{rt}</p>"
        f"<p>Depois disso o bot renova sozinho. Pode fechar.</p>")

@app.get("/qr", response_class=HTMLResponse)
def qr():
    """Mostra o QR da Evolution p/ escanear com o celular. Auto-atualiza."""
    import httpx
    if not settings.EVOLUTION_API_URL:
        return "Configure EVOLUTION_API_URL no Render."
    try:
        r = httpx.get(
            f"{settings.EVOLUTION_API_URL.rstrip('/')}/instance/connect/{settings.EVOLUTION_INSTANCE}",
            headers={"apikey": settings.EVOLUTION_APIKEY}, timeout=60)
        d = r.json()
    except Exception as e:
        return f"Falha ao buscar QR: {e}"
    img = d.get("base64", "")
    if not img:
        return f"Sem QR no momento: {d}"
    return f"""<html><head><meta http-equiv="refresh" content="25"></head>
    <body style="font-family:sans-serif;text-align:center">
    <h2>📱 Escaneie no WhatsApp</h2>
    <p>Aparelhos conectados → Conectar aparelho → aponte a câmera</p>
    <img src="{img}" width="320">
    <p><small>Atualiza sozinho a cada 25s. Se expirar, aguarde recarregar.</small></p>
    </body></html>"""

@app.get("/preview")
async def preview():
    from .scrapers.shopee import scan_all as scan_shopee
    from .scrapers.manual import load_manual
    try:
        offers = await scan_shopee(min_discount=0, per_query=5)
        src = "shopee-live"
    except Exception as e:
        offers = load_manual()
        src = f"manual-fallback ({e})"
    from .filter import format_msg
    return {"source": src, "count": len(offers),
            "items": [{"title": o.title, "price": o.price, "discount": o.discount_pct,
                       "cat": o.category, "url": o.url, "msg": format_msg(o)}
                      for o in offers[:10]]}
