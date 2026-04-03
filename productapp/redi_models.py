from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from redis_om import Field, JsonModel, Migrator, get_redis_connection


redis = get_redis_connection(
    host="localhost",
    port=6379,
    decode_responses=True,
)


class RedisBaseModel(JsonModel):
    class Meta:
        database = redis
        global_key_prefix = "redisboost"


class CustomerAnalyticsCache(JsonModel):
    customer_db_id: int = Field(index=True)
    full_name: str = Field(index=True, full_text_search=True)
    email: str = Field(index=True)
    total_orders: int = Field(index=True, default=0)
    delivered_orders: int = Field(index=True, default=0)
    canceled_orders: int = Field(index=True, default=0)
    total_spent: float = Field(index=True, default=0)
    avg_order_value: float = Field(index=True, default=0)

class ProductAnalyticsCache(JsonModel):
    product_db_id: int = Field(index=True)
    name: str = Field(index=True, full_text_search=True)
    brand: str = Field(index=True)
    total_quantity_sold: int = Field(index=True, default=0)
    total_revenue: float = Field(index=True, default=0)
    total_orders: int = Field(index=True, default=0)

class ProductSearchCache(JsonModel):
    product_db_id: int = Field(index=True)
    pid: str = Field(index=True, full_text_search=True)
    name: str = Field(index=True, full_text_search=True)
    description: str = Field(index=True, full_text_search=True)
    brand: str = Field(index=True)
    categories: List[str] = Field(index=True)
    retail_price: float = Field(index=True)
    discounted_price: float = Field(index=True)
    product_rating: Optional[str] = Field(index=True, default="")
    overall_rating: Optional[str] = Field(index=True, default="")
    is_fk_advantage_product: bool = Field(index=True, default=False)
    image_urls: List[str] = Field(default=[])



def run_redis_migrations():
    Migrator().run()