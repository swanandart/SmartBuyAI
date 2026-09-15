import os
import time
import httpx
from .base import Connector, Listing

class AmazonConnector(Connector):
    name = "Amazon"
    api_base = "https://creatorsapi.amazon"

    def __init__(self):
        self.client_id = os.getenv("AMAZON_CREATOR_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("AMAZON_CREATOR_CLIENT_SECRET", "").strip()
        self.partner_tag = os.getenv("AMAZON_PARTNER_TAG", "").strip()
        self.credential_version = os.getenv("AMAZON_CREDENTIAL_VERSION", "3.2").strip()
        self.marketplace = os.getenv("AMAZON_MARKETPLACE", "www.amazon.in").strip()
        self.token_endpoint = os.getenv("AMAZON_TOKEN_ENDPOINT", "https://api.amazon.co.uk/auth/o2/token").strip()
        self._token = None
        self._expires_at = 0
        self.configured = bool(self.client_id and self.client_secret and self.partner_tag)
        self.setup_message = "Ready" if self.configured else "Set Amazon Creators API credentials and partner tag in .env"

    def status(self):
        return {"retailer": self.name, "configured": self.configured, "message": self.setup_message, "api": self.api_base, "marketplace": self.marketplace}

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        r = await client.post(self.token_endpoint, json={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "creatorsapi::default",
        })
        r.raise_for_status()
        data = r.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._token

    @staticmethod
    def _image(item: dict) -> str | None:
        try:
            return item["images"]["primary"]["medium"]["url"]
        except Exception:
            return None

    @staticmethod
    def _price(item: dict) -> float | None:
        try:
            listings = item["offers"]["listings"]
            vals = []
            for listing in listings:
                p = listing.get("price", {}).get("amount")
                if p is not None:
                    vals.append(float(p))
            return min(vals) if vals else None
        except Exception:
            return None

    async def search(self, query: str) -> list[Listing]:
        if not self.configured:
            return []
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            token = await self._access_token(client)
            payload = {
                "partnerTag": self.partner_tag,
                "keywords": query,
                "searchIndex": "All",
                "itemCount": 10,
                "resources": [
                    "images.primary.medium",
                    "itemInfo.title",
                    "itemInfo.byLineInfo",
                    "offersV2.listings.price",
                    "offersV2.listings.availability",
                ],
            }
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "x-marketplace": self.marketplace}
            r = await client.post(f"{self.api_base}/catalog/v1/searchItems", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        out = []
        for item in data.get("searchResult", {}).get("items", []):
            title = item.get("itemInfo", {}).get("title", {}).get("displayValue") or "Unknown product"
            price = self._price(item)
            brand = None
            try:
                brand = item["itemInfo"]["byLineInfo"]["brand"]["displayValue"]
            except Exception:
                pass
            if price is None:
                continue
            out.append(Listing(
                retailer=self.name,
                external_id=str(item.get("asin", "")),
                title=title,
                price=price,
                mrp=None,
                shipping=0.0,
                delivery_days=None,
                seller_rating=None,
                product_rating=None,
                rating_count=None,
                discount_pct=None,
                image_url=self._image(item),
                product_url=item.get("detailPageURL"),
                brand=brand,
                category=None,
                availability=True,
                description="",
                raw=item,
            ))
        return out
