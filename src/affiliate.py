"""Injeta seu ID de afiliado Shopee nos links manuais."""
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
from .config import settings

def tag_url(url: str, source: str) -> str:
    try:
        u = urlparse(url)
        q = dict(parse_qsl(u.query))
        if source == "shopee" and settings.SHOPEE_AFFILIATE_ID:
            q["af_siteid"] = settings.SHOPEE_AFFILIATE_ID
        if not q:
            return url
        return urlunparse(u._replace(query=urlencode(q)))
    except Exception:
        return url
