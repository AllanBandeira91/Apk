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

@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <h2>🤖 Promo Bot — Moda Crente + Brinquedos</h2>
    <p>Grupos: {len(settings.groups)} | Intervalo: {settings.SCAN_INTERVAL_MIN}min</p>
    <p>Evolution: {'✅ configurada' if settings.EVOLUTION_API_URL else '❌ configure EVOLUTION_API_URL'}</p>
    <a href="/scan"><button>🔍 Buscar e postar agora</button></a> |
    <a href="/preview"><button>👀 Ver prévias sem postar</button></a>
    <p>Como conectar: suba a Evolution API, crie instance '{settings.EVOLUTION_INSTANCE}',
    leia o QR, crie o grupo e cole o JID em TARGET_GROUPS.</p>
    """

@app.get("/scan")
async def scan():
    return await run_scan()

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
