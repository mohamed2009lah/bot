import aiohttp
from config import API_KEY

async def shorten(url, alias=None):
    try:
        params = {"api": API_KEY, "url": url, "format": "json"}
        if alias:
            params["alias"] = alias
        async with aiohttp.ClientSession() as s:
            r = await s.get("https://shrinkearn.com/api", params=params)
            d = await r.json()
            if d.get("status") == "success":
                return d.get("shortenedUrl")
            return None
    except:
        return None

async def stats(url):
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.get("https://shrinkearn.com/api", params={
                "api": API_KEY, "url": url, "format": "json", "action": "stats"
            })
            d = await r.json()
            if d.get("status") == "success":
                return float(d.get("earned", 0))
    except:
        return None