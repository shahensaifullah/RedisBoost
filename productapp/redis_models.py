from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import ConfigDict
from redis_om import Field, JsonModel, Migrator, get_redis_connection


redis_db = get_redis_connection(
    host="localhost",
    port=6379,
    decode_responses=True,
)


class RedisBaseModel(JsonModel):
    """
    Shared base model for all Redis OM models.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    class Meta:
        database = redis_db
        global_key_prefix = "demo_shop"


class ProductCache(RedisBaseModel, index=True):
    """
    Denormalized product document for search/filter/sort.
    """
    django_id: int = Field(index=True, sortable=True)
    pid: str = Field(index=True)

    name: str = Field(full_text_search=True, sortable=True)
    description: str = Field(full_text_search=True, default="")

    brand_name: str = Field(index=True, default="")
    primary_category: str = Field(index=True, default="")

    # Full text helper for category search
    categories_text: str = Field(full_text_search=True, default="")

    retail_price: float = Field(sortable=True, default=0)
    discounted_price: float = Field(sortable=True, default=0)

    product_rating: str = Field(index=True, default="")
    overall_rating: str = Field(index=True, default="")
    is_fk_advantage_product: bool = Field(index=True, default=False)

    image_count: int = Field(sortable=True, default=0)
    created_at: Optional[datetime] = Field(sortable=True, default=None)
    crawl_timestamp: Optional[datetime] = Field(sortable=True, default=None)

    # Stored but not necessarily used in search
    category_names: list[str] = []
    image_urls: list[str] = []
    specifications: dict = {}
    product_url: str = ""

    class Meta(RedisBaseModel.Meta):
        model_key_prefix = "product"


class CustomerCache(RedisBaseModel, index=True):
    """
    Customer search + customer-level analytics snapshot.
    """
    django_id: int = Field(index=True, sortable=True)
    email: str = Field(index=True)
    full_name: str = Field(full_text_search=True, sortable=True)

    city: str = Field(index=True, default="")
    country: str = Field(index=True, default="")

    joined_at: Optional[datetime] = Field(sortable=True, default=None)

    order_count: int = Field(sortable=True, default=0)
    delivered_order_count: int = Field(sortable=True, default=0)
    canceled_order_count: int = Field(sortable=True, default=0)

    total_spent: float = Field(sortable=True, default=0)
    avg_order_value: float = Field(sortable=True, default=0)
    last_order_at: Optional[datetime] = Field(sortable=True, default=None)

    class Meta(RedisBaseModel.Meta):
        model_key_prefix = "customer"


class OrderCache(RedisBaseModel, index=True):
    """
    Denormalized order document for order search and analysis.
    """
    django_id: int = Field(index=True, sortable=True)
    customer_id: int = Field(index=True, sortable=True)
    customer_email: str = Field(index=True)
    customer_name: str = Field(full_text_search=True)

    status: str = Field(index=True)
    payment_method: str = Field(index=True, default="")
    transaction_id: str = Field(index=True, default="")

    city: str = Field(index=True, default="")
    country: str = Field(index=True, default="")

    subtotal: float = Field(sortable=True, default=0)
    discount_amount: float = Field(sortable=True, default=0)
    shipping_cost: float = Field(sortable=True, default=0)
    tax_amount: float = Field(sortable=True, default=0)
    total_amount: float = Field(sortable=True, default=0)

    placed_at: datetime = Field(sortable=True)
    paid_at: Optional[datetime] = Field(sortable=True, default=None)
    delivered_at: Optional[datetime] = Field(sortable=True, default=None)

    # Precomputed dimensions for analytics
    item_count: int = Field(sortable=True, default=0)
    total_quantity: int = Field(sortable=True, default=0)
    hour_of_day: int = Field(sortable=True, default=0)
    day_of_week: int = Field(sortable=True, default=0)   # Monday=0
    month: int = Field(sortable=True, default=0)
    year: int = Field(sortable=True, default=0)

    # Search helpers
    brand_names_text: str = Field(full_text_search=True, default="")
    category_names_text: str = Field(full_text_search=True, default="")
    product_names_text: str = Field(full_text_search=True, default="")

    # Stored raw-ish payload
    product_ids: list[str] = []
    product_names: list[str] = []
    category_names: list[str] = []
    brand_names: list[str] = []

    class Meta(RedisBaseModel.Meta):
        model_key_prefix = "order"


def run_redis_migrations() -> None:
    """
    Creates/updates RediSearch indexes for all indexed models.
    """
    Migrator().run()