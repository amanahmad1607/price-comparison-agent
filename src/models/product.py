"""
src/models/product.py
---------------------
Pydantic v2 models for the full data lifecycle:
  RawProduct → PlatformResult → NormalizedProduct → PlatformSummary → PriceComparison
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class RawProduct(BaseModel):
    platform: str
    product_id: str
    name: str
    brand: Optional[str] = None
    image_url: Optional[str] = None
    mrp: float
    selling_price: float
    discount_pct: float = 0.0
    quantity_str: str
    in_stock: bool = True
    delivery_time_min: Optional[int] = None
    product_url: str
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlatformResult(BaseModel):
    platform: str
    products: list[RawProduct] = Field(default_factory=list)
    error: Optional[str] = None
    latency_ms: float = 0.0


class NormalizedProduct(BaseModel):
    platform: str
    product_id: str
    name: str
    brand: Optional[str] = None
    image_url: Optional[str] = None
    mrp: float
    selling_price: float
    discount_pct: float
    quantity_value: float
    quantity_unit: str
    price_per_unit: float
    price_per_unit_label: str
    in_stock: bool
    delivery_time_min: Optional[int]
    product_url: str
    scraped_at: datetime


class PlatformSummary(BaseModel):
    platform: str
    best_price: float
    best_product_name: str
    best_product_url: str
    discount_pct: float
    price_per_unit: float
    price_per_unit_label: str
    in_stock: bool
    delivery_time_min: Optional[int] = None
    badge: Optional[str] = None


class PriceComparison(BaseModel):
    query: str
    platforms_searched: list[str]
    platforms_with_results: list[str]
    platform_summaries: list[PlatformSummary]
    cheapest_platform: Optional[str]
    fastest_delivery_platform: Optional[str]
    best_value_platform: Optional[str]
    all_products: list[NormalizedProduct]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cache_key: Optional[str] = None
