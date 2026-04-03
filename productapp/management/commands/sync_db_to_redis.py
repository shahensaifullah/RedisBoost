from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db.models import Count, Max, Q, Sum

from productapp.models import Customer, Order, Product
from productapp.redis_models import (
    CustomerCache,
    OrderCache,
    ProductCache,
    run_redis_migrations,
)


def to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError, InvalidOperation):
        return 0.0


def clean_str(value, default: str = "") -> str:
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def unique_keep_order(values: list[str]) -> list[str]:
    cleaned = []
    for value in values:
        item = clean_str(value)
        if item:
            cleaned.append(item)
    return list(dict.fromkeys(cleaned))


class Command(BaseCommand):
    help = "Sync Django database data into Redis OM cache for search and analytics."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true")
        parser.add_argument("--products-only", action="store_true")
        parser.add_argument("--customers-only", action="store_true")
        parser.add_argument("--orders-only", action="store_true")

    def handle(self, *args, **options):
        flush = options["flush"]
        products_only = options["products_only"]
        customers_only = options["customers_only"]
        orders_only = options["orders_only"]

        run_redis_migrations()

        if flush:
            self.stdout.write(self.style.WARNING("Flushing Redis documents..."))
            self._delete_all(ProductCache)
            self._delete_all(CustomerCache)
            self._delete_all(OrderCache)

        if not customers_only and not orders_only:
            self.sync_products()

        if not products_only and not orders_only:
            self.sync_customers()

        if not products_only and not customers_only:
            self.sync_orders()

        self.stdout.write(self.style.SUCCESS("Redis sync finished."))

    def _delete_all(self, model_cls):
        try:
            model_cls.find().delete()
        except Exception:
            redis_conn = model_cls.db()
            key_prefix = getattr(model_cls.Meta, "global_key_prefix", "")
            model_prefix = getattr(model_cls.Meta, "model_key_prefix", "")
            pattern = f"{key_prefix}:{model_prefix}:*"

            cursor = 0
            while True:
                cursor, keys = redis_conn.scan(cursor=cursor, match=pattern, count=500)
                if keys:
                    redis_conn.delete(*keys)
                if cursor == 0:
                    break

    def sync_products(self):
        self.stdout.write("Syncing products...")

        qs = (
            Product.objects
            .select_related("brand")
            .prefetch_related("categories", "images")
            .iterator(chunk_size=500)
        )

        created_count = 0
        skipped_count = 0

        for product in qs:
            # try:
            pid = product.pid
            name = product.name
            description = product.description
            brand_name = product.brand.name
            product_url = product.product_url

            category_names = unique_keep_order(
                list(product.categories.values_list("name", flat=True))
            )
            if not category_names:
                category_names = ["Uncategorized"]

            image_urls = unique_keep_order(
                list(product.images.values_list("image", flat=True))
            )
            # find_product = ProductCache.find(ProductCache.django_id == product.id)
            # if find_product.count() > 0:
            #     find_product.delete()

            ProductCache(
                django_id=product.id,
                pid=pid,
                name=name,
                description=description,
                brand_name=brand_name,
                primary_category=category_names[0],
                categories_text=" ".join(category_names),
                retail_price=to_float(product.retail_price),
                discounted_price=to_float(product.discounted_price),
                product_rating=clean_str(product.product_rating, default="0"),
                overall_rating=clean_str(product.overall_rating, default="0"),
                is_fk_advantage_product=bool(product.is_fk_advantage_product),
                image_count=len(image_urls),
                created_at=product.created_at,
                crawl_timestamp=product.crawl_timestamp,
                category_names=category_names,
                image_urls=image_urls,
                specifications=product.product_specifications or {},
                product_url=product_url,
            ).save()

            created_count += 1

            # except Exception as exc:
            #     skipped_count += 1
            #     self.stdout.write(
            #         self.style.WARNING(
            #             f"Skipping product id={product.id} because error: {exc}"
            #         )
            #     )

        self.stdout.write(
            self.style.SUCCESS(
                f"Products synced: {created_count}, skipped: {skipped_count}"
            )
        )

    def sync_customers(self):
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

        created_count = 0
        skipped_count = 0

        for customer in qs:
            # try:
            # find_old_customer = CustomerCache.find(CustomerCache.django_id == customer.id)
            # if find_old_customer.count() > 0:
            #     find_old_customer.delete()

            order_count = customer.order_count_agg or 0
            total_spent = to_float(customer.total_spent_agg or 0)
            avg_order_value = total_spent / order_count if order_count else 0.0

            CustomerCache(
                django_id=customer.id,
                email=clean_str(customer.email, default=f"unknown-{customer.id}@example.com"),
                full_name=clean_str(customer.full_name, default=f"Customer {customer.id}"),
                city=clean_str(customer.city, default="Unknown"),
                country=clean_str(customer.country, default="Unknown"),
                joined_at=customer.joined_at,
                order_count=order_count,
                delivered_order_count=customer.delivered_order_count_agg or 0,
                canceled_order_count=customer.canceled_order_count_agg or 0,
                total_spent=total_spent,
                avg_order_value=avg_order_value,
                last_order_at=customer.last_order_at_agg,
            ).save()

            created_count += 1

            # except Exception as exc:
            #     skipped_count += 1
            #     self.stdout.write(
            #         self.style.WARNING(
            #             f"Skipping customer id={customer.id} because error: {exc}"
            #         )
            #     )

        self.stdout.write(
            self.style.SUCCESS(
                f"Customers synced: {created_count}, skipped: {skipped_count}"
            )
        )

    def sync_orders(self):
        self.stdout.write("Syncing orders...")

        qs = (
            Order.objects
            .select_related("customer")
            .prefetch_related("items__product__brand", "items__product__categories")
            .iterator(chunk_size=200)
        )

        created_count = 0
        skipped_count = 0

        for order in qs:
            # try:
            items = list(order.items.all())

            product_ids = []
            product_names = []
            brand_names = []
            category_names = []
            total_quantity = 0

            for item in items:
                total_quantity += item.quantity

                product_ids.append(
                    clean_str(item.product.pid, default=f"unknown-pid-product-{item.product_id}")
                )
                product_names.append(
                    clean_str(item.product.name, default=f"Unnamed Product {item.product_id}")
                )

                brand_names.append(
                    clean_str(
                        item.product.brand.name if item.product.brand else "",
                        default="Unknown",
                    )
                )

                item_category_names = unique_keep_order(
                    list(item.product.categories.values_list("name", flat=True))
                )
                if not item_category_names:
                    item_category_names = ["Uncategorized"]

                category_names.extend(item_category_names)

            product_ids = unique_keep_order(product_ids) or [f"unknown-order-{order.id}"]
            product_names = unique_keep_order(product_names) or [f"Order Product {order.id}"]
            brand_names = unique_keep_order(brand_names) or ["Unknown"]
            category_names = unique_keep_order(category_names) or ["Uncategorized"]

            placed_at = order.placed_at
            if placed_at is None:
                raise ValueError("placed_at cannot be empty")

            # find_order_old = OrderCache.find(OrderCache.django_id == order.id)
            # if find_order_old.count() > 0:
            #     find_order_old.delete()

            OrderCache(
                django_id=order.id,
                customer_id=order.customer_id,
                customer_email=clean_str(order.customer.email, default=f"unknown-{order.customer_id}@example.com"),
                customer_name=clean_str(order.customer.full_name, default=f"Customer {order.customer_id}"),
                status=clean_str(order.status, default="unknown"),
                payment_method=clean_str(order.payment_method, default="unknown"),
                transaction_id=clean_str(order.transaction_id, default=""),
                city=clean_str(order.customer.city, default="Unknown"),
                country=clean_str(order.customer.country, default="Unknown"),
                subtotal=to_float(order.subtotal),
                discount_amount=to_float(order.discount_amount),
                shipping_cost=to_float(order.shipping_cost),
                tax_amount=to_float(order.tax_amount),
                total_amount=to_float(order.total_amount),
                placed_at=placed_at,
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

            created_count += 1

            # except Exception as exc:
            #     skipped_count += 1
            #     self.stdout.write(
            #         self.style.WARNING(
            #             f"Skipping order id={order.id} because error: {exc}"
            #         )
            #     )

        self.stdout.write(
            self.style.SUCCESS(
                f"Orders synced: {created_count}, skipped: {skipped_count}"
            )
        )