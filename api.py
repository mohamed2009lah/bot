import aiohttp
from config import API_KEY

async def shorten(url):
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.get(
                "https://shrinkearn.com/api",
                params={"api": API_KEY, "url": url, "format": "json"}
            )
            d = await r.json()
            return d.get("shortenedUrl")
    except:
        return None


async def stats(url):
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.get(
                "https://shrinkearn.com/api",
                params={
                    "api": API_KEY,
                    "url": url,
                    "format": "json",
                    "action": "stats"
                }
            )
            d = await r.json()
            if d.get("status") == "success":
                return float(d.get("earned", 0))
    except:
        return None
