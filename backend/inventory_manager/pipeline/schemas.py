from dataclasses import dataclass
from decimal import Decimal

@dataclass
class Listing:
    title: str
    price: Decimal
    condition: str | None
    listing_id: str = ""
    url: str = ""