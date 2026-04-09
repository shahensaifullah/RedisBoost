from __future__ import annotations

from datetime import datetime

from pydantic import ConfigDict
from redis_om import Field, JsonModel, Migrator, get_redis_connection


redis_db = get_redis_connection(
    host="localhost",
    port=6379,
    decode_responses=True,
)


class RedisBaseModel(JsonModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    class Meta:
        database = redis_db
        global_key_prefix = "demo_shop"

from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime

from pydantic import ConfigDict
from redis_om import JsonModel, EmbeddedJsonModel, Field


class BrandData(EmbeddedJsonModel):
    id: int = Field(index=True)
    name: str = Field(index=True, full_text_search=True)



class CategoryData(EmbeddedJsonModel):
    id: int = Field(default=None, index=True)
    name: str = Field(index=True, full_text_search=True)



class ProductCache(JsonModel, index=True):
    django_id: int = Field(index=True)
    pid: str = Field(index=True)
    crawl_timestamp: Optional[datetime] = Field(default=None, index=True)

    name: str = Field(index=True, full_text_search=True)
    description: Optional[str] = Field(default="")

    brand: BrandData
    categories: List[dict]

    retail_price: Decimal = Field(default=Decimal("0.00"), index=True)
    discounted_price: Decimal = Field(default=Decimal("0.00"), index=True)

    product_rating: Optional[str] = Field(default="", index=True)
    overall_rating: Optional[str] = Field(default="", index=True)

    is_fk_advantage_product: bool = Field(default=False, index=True)
    images: Optional[List[str]] = None

    created_at: Optional[datetime] = Field(default=None, index=True)

#
class CustomerCache(RedisBaseModel, index=True):
    django_id: int = Field(index=True, sortable=True)
    email: str = Field(index=True, default="")
    full_name: str = Field(full_text_search=True, sortable=True, default="")

    city: str = Field(index=True, default="")
    country: str = Field(index=True, default="")

    joined_at: datetime | None = Field(sortable=True, default=None)

    order_count: int = Field(sortable=True, default=0)
    delivered_order_count: int = Field(sortable=True, default=0)
    canceled_order_count: int = Field(sortable=True, default=0)

    total_spent: float = Field(sortable=True, default=0)
    avg_order_value: float = Field(sortable=True, default=0)
    last_order_at: datetime | None = Field(sortable=True, default=None)

    class Meta(RedisBaseModel.Meta):
        model_key_prefix = "customer"
#
#
class OrderCache(RedisBaseModel, index=True):
    django_id: int = Field(index=True, sortable=True)
    customer_id: int = Field(index=True, sortable=True)
    customer_email: str = Field(index=True, default="")
    customer_name: str = Field(full_text_search=True, default="")

    status: str = Field(index=True, default="")
    payment_method: str = Field(index=True, default="")
    transaction_id: str = Field(index=True, default="")

    city: str = Field(index=True, default="")
    country: str = Field(index=True, default="")

    subtotal: float = Field(sortable=True, default=0)
    discount_amount: float = Field(sortable=True, default=0)
    shipping_cost: float = Field(sortable=True, default=0)
    tax_amount: float = Field(sortable=True, default=0)
    total_amount: float = Field(sortable=True, default=0)

    placed_at: datetime | None = Field(sortable=True, default=None)
    paid_at: datetime | None = Field(sortable=True, default=None)
    delivered_at: datetime | None = Field(sortable=True, default=None)

    item_count: int = Field(sortable=True, default=0)
    total_quantity: int = Field(sortable=True, default=0)
    hour_of_day: int = Field(sortable=True, default=0)
    day_of_week: int = Field(sortable=True, default=0)
    month: int = Field(sortable=True, default=0)
    year: int = Field(sortable=True, default=0)

    brand_names_text: str = Field(full_text_search=True, default="")
    category_names_text: str = Field(full_text_search=True, default="")
    product_names_text: str = Field(full_text_search=True, default="")

    product_ids: list[str] = Field(default_factory=list)
    product_names: list[str] = Field(default_factory=list)
    category_names: list[str] = Field(default_factory=list)
    brand_names: list[str] = Field(default_factory=list)

    class Meta(RedisBaseModel.Meta):
        model_key_prefix = "order"


def run_redis_migrations() -> None:
    Migrator().run()