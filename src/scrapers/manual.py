"""Backup que SEMPRE funciona: cole links na ofertas.csv e o bot formata+posta sozinho.

Formato ofertas.csv (cabeçalho):
title,price,original_price,url,image,source
Ex:
Vestido Longo Evangelica Floral,89.90,129.90,https://seulinkafiliado.com/x,https://img...,shopee
"""
import csv, pathlib
from ..filter import Offer, classify
from ..affiliate import tag_url

CSV = pathlib.Path("ofertas.csv")

def load_manual() -> list[Offer]:
    if not CSV.exists():
        return []
    out: list[Offer] = []
    for row in csv.DictReader(CSV.read_text(encoding="utf-8").splitlines()):
        title = (row.get("title") or "").strip()
        if not title:
            continue
        raw_url = (row.get("url") or "").strip()
        if not raw_url or "exemplo" in raw_url.lower():
            continue  # pula placeholders/linhas de exemplo
        cat = classify(title) or (row.get("category") or "").strip() or "moda"
        if classify(title) is None and not row.get("category"):
            continue  # fora do nicho
        try:
            price = float(str(row.get("price") or 0).replace("R$", "").replace(",", ".").strip())
        except ValueError:
            continue
        orig = (row.get("original_price") or "").strip()
        out.append(Offer(
            title=title, price=price,
            original_price=float(orig.replace(",", ".")) if orig else None,
            url=tag_url((row.get("url") or "").strip(), (row.get("source") or "shopee").strip()),
            image=(row.get("image") or "").strip(),
            source=(row.get("source") or "shopee").strip(),
            category=cat,
        ))
    return out
