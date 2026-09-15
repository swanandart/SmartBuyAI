import os
import httpx
from .base import Connector, Listing

class JsonFeedConnector(Connector):
    feed_env = ""
    name = "Feed"

    def __init__(self):
        self.feed_url = os.getenv(self.feed_env, "").strip()
        self.configured = bool(self.feed_url)
        self.setup_message = "Configured JSON feed" if self.configured else f"Set {self.feed_env} to an approved retailer/partner JSON feed"

    def status(self):
        return {"retailer": self.name, "configured": self.configured, "message": self.setup_message}

    async def search(self, query: str) -> list[Listing]:
        if not self.configured:
            return []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(self.feed_url, params={"q": query})
            r.raise_for_status()
            data = r.json()
        rows = data.get("products", data if isinstance(data, list) else [])
        q = query.lower().strip()
        out=[]
        for x in rows:
            title=str(x.get("title") or x.get("name") or "").strip()
            if q and q not in title.lower() and not any(tok in title.lower() for tok in q.split()):
                continue
            price=x.get("price") or x.get("selling_price") or x.get("salePrice")
            if price is None: continue
            out.append(Listing(
                retailer=self.name,
                external_id=str(x.get("id") or x.get("sku") or x.get("productId") or title),
                title=title,
                price=float(price),
                mrp=float(x["mrp"]) if x.get("mrp") is not None else None,
                shipping=float(x.get("shipping") or 0),
                delivery_days=int(x["delivery_days"]) if x.get("delivery_days") is not None else None,
                seller_rating=float(x["seller_rating"]) if x.get("seller_rating") is not None else None,
                product_rating=float(x["rating"]) if x.get("rating") is not None else None,
                rating_count=int(x["rating_count"]) if x.get("rating_count") is not None else None,
                discount_pct=float(x["discount_pct"]) if x.get("discount_pct") is not None else None,
                image_url=x.get("image_url") or x.get("image"),
                product_url=x.get("product_url") or x.get("url"),
                brand=x.get("brand"), category=x.get("category"), availability=x.get("availability", True),
                description=x.get("description", ""), raw=x,
            ))
        return out

class CromaConnector(JsonFeedConnector):
    name = "Croma"
    feed_env = "CROMA_FEED_URL"

class RelianceDigitalConnector(JsonFeedConnector):
    name = "Reliance Digital"
    feed_env = "RELIANCE_DIGITAL_FEED_URL"
