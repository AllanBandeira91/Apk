# 🤖 Grupo de Promoções WhatsApp — Ofertas Shopee (Automático)

Sistema que **captura ofertas sozinho** (Shopee em tempo real) e **posta no seu grupo de WhatsApp** via Evolution API. Pronto pro **Render grátis**.

## 1. O que você precisa (1x só)
1. Conta afiliado Shopee (cola APPID/SECRET no `.env`)
2. Subir a **Evolution API** no Render (é o "chip virtual" do bot — WhatsApp oficial não deixa bot postar em grupo, então usa ela):
   - Suba `evoapicloud/evolution-api` como Web Service
   - Crie instance `promocoes` → conecte o número → crie o grupo
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
`APScheduler` (a cada SCAN_INTERVAL_MIN) → `scrapers/shopee.py` busca em rodízio
→ `filter.py` classifica em 5 seções (moda/calçados/acessórios/kids/bebê, sem repetidos)
→ `sender.py` manda imagem+legenda no grupo via Evolution
→ `posted.json` + `sent_history.json` evitam repetir oferta.

## 5. Shopee (✅ plugada e testada)
`scrapers/shopee.py` usa a Affiliate Open API oficial (GraphQL):
busca por palavra-chave → filtra → gera **shortlink com sua comissão** (`s.shopee.com.br/...`).
No Render, configure `SHOPEE_APPID` + `SHOPEE_SECRET` como variáveis de ambiente
(nunca commite o secret no git).

⚠️ **Risco de ban:** use 1 número exclusivo pro bot e volume moderado. Não use seu número pessoal.
