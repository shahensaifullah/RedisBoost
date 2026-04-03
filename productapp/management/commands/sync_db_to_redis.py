from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.core.management.base import BaseCommand
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from productapp.models import Customer, Order, Product
from productapp.redis_models import (
    CustomerCache,
    OrderCache,
    ProductCache,
    run_redis_migrations, redis_db,
)


def to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


class Command(BaseCommand):
    help = "Sync Django database data into Redis OM cache for search and analytics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing Redis OM documents before resync.",
        )
        parser.add_argument(
            "--products-only",
            action="store_true",
            help="Sync only products.",
        )
        parser.add_argument(
            "--customers-only",
            action="store_true",
            help="Sync only customers.",
        )
        parser.add_argument(
            "--orders-only",
            action="store_true",
            help="Sync only orders.",
        )

    def handle(self, *args, **options):
        flush = options["flush"]
        products_only = options["products_only"]
        customers_only = options["customers_only"]
        orders_only = options["orders_only"]

        run_redis_migrations()

        if flush:
            self.stdout.write(self.style.WARNING("Flushing Redis OM documents..."))
            ProductCache.find().delete()
            CustomerCache.find().delete()
            OrderCache.find().delete()

        if not customers_only and not orders_only:
            self.sync_products()

        if not products_only and not orders_only:
            self.sync_customers()

        if not products_only and not customers_only:
            self.sync_orders()

        self.stdout.write(self.style.SUCCESS("Redis sync finished."))

    def sync_products(self) -> None:
        self.stdout.write("Syncing products...")

        qs = (
            Product.objects
            .select_related("brand")
            .prefetch_related("categories", "images")
            .iterator(chunk_size=500)
        )

        count = 0
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
                retail_price=to_float(product.retail_price),
                discounted_price=to_float(product.discounted_price),
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

            count += 1

        self.stdout.write(self.style.SUCCESS(f"Products synced: {count}"))

    def sync_customers(self) -> None:
        self.stdout.write("Syncing customers...")

        qs = (
            Customer.objects
            .annotate(
                order_count_agg=Count("orders", distinct=True),
                delivered_order_count_agg=Count(
                    "orders",
                    filter=Q(orders__status="delivered"),
                    distinct=True,
                ),
                canceled_order_count_agg=Count(
                    "orders",
                    filter=Q(orders__status="canceled"),
                    distinct=True,
                ),
                total_spent_agg=Sum(
                    "orders__total_amount",
                    filter=Q(orders__status__in=["paid", "shipped", "delivered"]),
                ),
                last_order_at_agg=Max("orders__placed_at"),
            )
            .iterator(chunk_size=500)
        )

        count = 0
        for customer in qs:
            order_count = customer.order_count_agg or 0
            total_spent = to_float(customer.total_spent_agg or 0)
            avg_order_value = total_spent / order_count if order_count else 0.0

            CustomerCache(
                django_id=customer.id,
                email=customer.email,
                full_name=customer.full_name,
                city=customer.city or "",
                country=customer.country or "",
                joined_at=customer.joined_at,
                order_count=order_count,
                delivered_order_count=customer.delivered_order_count_agg or 0,
                canceled_order_count=customer.canceled_order_count_agg or 0,
                total_spent=total_spent,
                avg_order_value=avg_order_value,
                last_order_at=customer.last_order_at_agg,
            ).save()

            count += 1

        self.stdout.write(self.style.SUCCESS(f"Customers synced: {count}"))

    def sync_orders(self) -> None:
        self.stdout.write("Syncing orders...")

        qs = (
            Order.objects
            .select_related("customer")
            .prefetch_related("items__product__brand", "items__product__categories")
            .iterator(chunk_size=200)
        )

        count = 0
        for order in qs:
            items = list(order.items.all())

            product_ids: list[str] = []
            product_names: list[str] = []
            brand_names: list[str] = []
            category_names: list[str] = []

            total_quantity = 0

            for item in items:
                total_quantity += item.quantity
                product_ids.append(item.product.pid)
                product_names.append(item.product.name)

                if item.product.brand and item.product.brand.name:
                    brand_names.append(item.product.brand.name)

                item_categories = list(item.product.categories.values_list("name", flat=True))
                category_names.extend(item_categories)

            # dedupe but keep order
            brand_names = list(dict.fromkeys(brand_names))
            category_names = list(dict.fromkeys(category_names))
            product_names = list(dict.fromkeys(product_names))
            product_ids = list(dict.fromkeys(product_ids))

            placed_at = order.placed_at

            OrderCache(
                django_id=order.id,
                customer_id=order.customer_id,
                customer_email=order.customer.email,
                customer_name=order.customer.full_name,
                status=order.status,
                payment_method=order.payment_method or "",
                transaction_id=order.transaction_id or "",
                city=order.customer.city or "",
                country=order.customer.country or "",
                subtotal=to_float(order.subtotal),
                discount_amount=to_float(order.discount_amount),
                shipping_cost=to_float(order.shipping_cost),
                tax_amount=to_float(order.tax_amount),
                total_amount=to_float(order.total_amount),
                placed_at=order.placed_at,
                paid_at=order.paid_at,
                delivered_at=order.delivered_at,
                item_count=len(items),
                total_quantity=total_quantity,
                hour_of_day=placed_at.hour,
                day_of_week=placed_at.weekday(),
                month=placed_at.month,
                year=placed_at.year,
                brand_names_text=" ".join(brand_names),
                category_names_text=" ".join(category_names),
                product_names_text=" ".join(product_names),
                product_ids=product_ids,
                product_names=product_names,
                category_names=category_names,
                brand_names=brand_names,
            ).save()

            count += 1

        self.stdout.write(self.style.SUCCESS(f"Orders synced: {count}"))
