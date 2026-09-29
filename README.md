# 🤖 Grupo de Promoções WhatsApp — Moda Crente + Brinquedos (Automático)

Sistema que **captura ofertas sozinho** (Mercado Livre em tempo real) e **posta no seu grupo de WhatsApp** via Evolution API. Pronto pro **Render grátis**.

## 1. O que você precisa (1x só)
1. Conta afiliado: Mercado Livre, Shopee, Amazon, AliExpress (cola os IDs no `.env`)
2. Subir a **Evolution API** no Render (é o "chip virtual" do bot — WhatsApp oficial não deixa bot postar em grupo, então usa ela):
   - Suba `https://github.com/EvolutionAPI/evolution-api` como Web Service
   - Crie instance `promocoes` → leia o QR com seu WhatsApp → crie o grupo
3. Subir este projeto no Render (Docker, plano free)

## 2. Rodar local / testar
```bash
pip install -r requirements.txt
python -m uvicorn src.server:app --reload
# abra http://localhost:8000/preview  (vê ofertas sem postar)
```

## 3. Deploy no Render
- New → Web Service → conecte seu GitHub com esta pasta
- Runtime: Docker. Variáveis (copie do `.env.example`):
  `EVOLUTION_API_URL, EVOLUTION_APIKEY, EVOLUTION_INSTANCE, TARGET_GROUPS, *_TAG/ID`
- Deploy. Acesse `sua-url.onrender.com/scan` 1x pra testar.

## 4. Como funciona
`APScheduler` (a cada SCAN_INTERVAL_MIN) → `scrapers/mercadolivre.py` busca 8 termos
→ `filter.py` aprova só moda modesta (bloqueia curto/decotado) + brinquedos
→ `affiliate.py` injeta seu link de afiliado
→ `sender.py` manda imagem+legenda no grupo via Evolution
→ `posted.json` evita repetir oferta.

## 5. Shopee (✅ já plugada e testada)
`scrapers/shopee.py` usa a Affiliate Open API oficial (GraphQL):
busca por palavra-chave nos 2 nichos → filtra → gera **shortlink com sua comissão** (`s.shopee.com.br/...`).
No Render, configure `SHOPEE_APPID` + `SHOPEE_SECRET` como variáveis de ambiente
(nunca commite o secret no git).

## 6. Mercado Livre / Amazon / Ali (opcional)
ML já vem funcionando sem chave. Shopee exige `appid/secret` do Open Platform e Amazon exige PA-API — me passe suas credenciais de afiliado que eu plugo os 3 aqui no mesmo `scan_all()`.

⚠️ **Risco de ban:** use 1 número exclusivo pro bot, intervalo ≥ 60min, máx 6 msgs/varredura (já configurado). Não use seu número pessoal.
