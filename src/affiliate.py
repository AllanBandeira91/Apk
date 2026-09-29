"""Injeta seu ID de afiliado nos links."""
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
from .config import settings

def tag_url(url: str, source: str) -> str:
    try:
        u = urlparse(url)
        q = dict(parse_qsl(u.query))
        if source == "ml" and settings.ML_AFFILIATE_TAG:
            q["matt_tool"] = settings.ML_AFFILIATE_TAG
        elif source == "amazon" and settings.AMAZON_TAG:
            q["tag"] = settings.AMAZON_TAG
        elif source == "shopee" and settings.SHOPEE_AFFILIATE_ID:
            q["af_siteid"] = settings.SHOPEE_AFFILIATE_ID
        elif source == "aliexpress" and settings.ALIEXPRESS_AFF_ID:
            q["aff_fcid"] = settings.ALIEXPRESS_AFF_ID
        if not q:
            return url
        return urlunparse(u._replace(query=urlencode(q)))
    except Exception:
        return url
