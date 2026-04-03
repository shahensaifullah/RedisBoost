from celery import shared_task
from django.db.models import Prefetch

from .models import Product
from .redis_models import ProductCache, run_redis_migrations


@shared_task(ignore_result=True)
def cache_all_products_task() -> None:
    """
    Backfill all products from Django DB into Redis.
    Safe to call multiple times for demo purposes.
    """
    run_redis_migrations()

    qs = (
        Product.objects
        .select_related("brand")
        .prefetch_related("categories", "images")
        .iterator(chunk_size=500)
    )

    for product in qs:
        category_names = list(product.categories.values_list("name", flat=True))
        image_urls = list(product.images.values_list("image", flat=True))

        ProductCache(
            django_id=product.id,
            pid=product.pid,
            name=product.name,
            description=product.description or "",
            brand_name=product.brand.name if product.brand else "",
            primary_category=category_names[0] if category_names else "",
            categories_text=" ".join(category_names),
            retail_price=float(product.retail_price or 0),
            discounted_price=float(product.discounted_price or 0),
            product_rating=product.product_rating or "",
            overall_rating=product.overall_rating or "",
            is_fk_advantage_product=product.is_fk_advantage_product,
            image_count=len(image_urls),
            created_at=product.created_at,
            crawl_timestamp=product.crawl_timestamp,
            category_names=category_names,
            image_urls=image_urls,
            specifications=product.product_specifications or {},
            product_url=product.product_url or "",
        ).save()