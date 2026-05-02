"""
src/models/query.py
-------------------
Pydantic v2 model for the parsed user query.
Only Zepto and Blinkit are supported platforms.
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, field_validator

ALL_PLATFORMS = ["zepto", "blinkit"]

UNIT_ALIASES: dict[str, str] = {
    "ml": "ml",
    "l": "L", "litre": "L", "liter": "L",
    "g": "g", "gm": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilogram": "kg",
    "pack": "pack", "pkt": "pack", "packet": "pack",
    "piece": "piece", "pcs": "piece", "pc": "piece",
}


class ParsedQuery(BaseModel):
    product_name: str
    brand: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    max_price: Optional[float] = None
    platforms: list[str] = Field(default_factory=list)
    raw: str

    @field_validator("unit", mode="before")
    @classmethod
    def normalise_unit(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return UNIT_ALIASES.get(v.strip().lower(), v.strip().lower())

    @field_validator("platforms", mode="before")
    @classmethod
    def validate_platforms(cls, v: list[str]) -> list[str]:
        return [p.lower() for p in v if p.lower() in ALL_PLATFORMS]

    @property
    def search_string(self) -> str:
        parts = []
        if self.brand:
            parts.append(self.brand)
        parts.append(self.product_name)
        if self.quantity and self.unit:
            parts.append(f"{int(self.quantity)}{self.unit}")
        return " ".join(parts)
