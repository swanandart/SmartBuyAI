import os
from typing import Any
import httpx
from .base import Connector, Listing

class FlipkartConnector(Connector):
    name = "Flipkart"
    base_url = "https://affiliate-api.flipkart.net/affiliate/1.0/search.json"

    def __init__(self):
        self.affiliate_id = os.getenv("FLIPKART_AFFILIATE_ID", "").strip()
        self.token = os.getenv("FLIPKART_AFFILIATE_TOKEN", "").strip()
        self.configured = bool(self.affiliate_id and self.token)
        self.setup_message = "Ready" if self.configured else "Set FLIPKART_AFFILIATE_ID and FLIPKART_AFFILIATE_TOKEN in .env"

    def status(self):
        return {"retailer": self.name, "configured": self.configured, "message": self.setup_message, "api": self.base_url}

    @staticmethod
    def _first_image(images: Any) -> str | None:
        if not isinstance(images, dict):
            return None
        for key in ("400x400", "275x340", "275x275", "200x200", "unknown"):
            if images.get(key):
                return images[key]
        return next((v for v in images.values() if isinstance(v, str) and v), None)

    @staticmethod
    def _category(attrs: dict) -> str:
        paths = attrs.get("categoryPaths", {}).get("categoryPath", [])
        try:
            raw = paths[0][0].get("title", "") if paths and isinstance(paths[0], list) else ""
            return raw.split(">")[-1].strip() or "Other"
        except Exception:
            return "Other"

    async def search(self, query: str) -> list[Listing]:
        if not self.configured:
            return []
        headers = {"Fk-Affiliate-Id": self.affiliate_id, "Fk-Affiliate-Token": self.token}
        params = {"query": query, "resultCount": 10}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(self.base_url, params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        out: list[Listing] = []
        for item in data.get("productInfoList", []):
            attrs = item.get("productBaseInfoV1") or item.get("productBaseInfo", {}).get("productAttributes", {})
            if not attrs:
                continue
            price = (attrs.get("sellingPrice") or {}).get("amount")
            mrp = (attrs.get("maximumRetailPrice") or {}).get("amount")
            shipping = 0.0
            ship = item.get("productShippingInfoV1") or item.get("productShippingBaseInfo") or {}
            delivery = ship.get("estimatedDeliveryTime") or ship.get("deliveryTime")
            if isinstance(delivery, str):
                import re
                m = re.search(r"(\d+)", delivery)
                delivery = int(m.group(1)) if m else None
            discount = attrs.get("discountPercentage")
            out.append(Listing(
                retailer=self.name,
                external_id=str(attrs.get("productId") or ""),
                title=attrs.get("title") or "Unknown product",
                price=float(price) if price is not None else None,
                mrp=float(mrp) if mrp is not None else None,
                shipping=shipping,
                delivery_days=delivery,
                seller_rating=None,
                product_rating=None,
                discount_pct=float(discount) if discount is not None else None,
                image_url=self._first_image(attrs.get("imageUrls")),
                product_url=attrs.get("productUrl"),
                brand=attrs.get("productBrand"),
                category=self._category(attrs),
                availability=attrs.get("inStock", attrs.get("isAvailable")),
                description=attrs.get("productDescription", ""),
                raw=item,
            ))
        return [x for x in out if x.price is not None]
