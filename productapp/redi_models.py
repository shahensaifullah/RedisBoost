from datetime import datetime
from decimal import Decimal
from typing import Optional

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


class ProductCache(RedisBaseModel, index=True):
    product_id: str = Field(index=True)
    name: str = Field(full_text_search=True)

    class Meta(RedisBaseModel.Meta):
        model_key_prefix = "product"


class CustomerCache(RedisBaseModel, index=True):
    user_id: str = Field(index=True)
    profile_name: Optional[str] = Field(default=None, full_text_search=True)

    class Meta(RedisBaseModel.Meta):
        model_key_prefix = "customer"


class ReviewCache(RedisBaseModel, index=True):
    external_id: int = Field(index=True, sortable=True)

    help_numerator: int = Field(default=0, sortable=True)
    help_denominator: int = Field(default=0, sortable=True)
    score: float = Field(index=True, sortable=True)

    review_time: datetime = Field(index=True, sortable=True)

    summary: Optional[str] = Field(default=None, full_text_search=True)
    text: str = Field(full_text_search=True)

    product_id: str = Field(index=True)
    product_name: str = Field(full_text_search=True)

    user_id: str = Field(index=True)
    profile_name: Optional[str] = Field(default=None, full_text_search=True)

    class Meta(RedisBaseModel.Meta):
        model_key_prefix = "review"


def run_redis_migrations():
    Migrator().run()