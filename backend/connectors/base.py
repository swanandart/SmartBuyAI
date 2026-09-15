from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class Listing:
    retailer: str
    external_id: str
    title: str
    price: Optional[float] = None
    mrp: Optional[float] = None
    shipping: float = 0.0
    delivery_days: Optional[int] = None
    seller_rating: Optional[float] = None
    product_rating: Optional[float] = None
    rating_count: Optional[int] = None
    discount_pct: Optional[float] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    availability: Optional[bool] = None
    description: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

class Connector:
    name = "Unknown"
    configured = False
    setup_message = "Not configured"

    def status(self) -> dict[str, Any]:
        return {"retailer": self.name, "configured": self.configured, "message": self.setup_message}

    async def search(self, query: str) -> list[Listing]:
        raise NotImplementedError
