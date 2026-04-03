import ast
import csv
import os
import random
import shutil
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import kagglehub
from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from faker import Faker
from tqdm import tqdm

from productapp.models import (
    Brand,
    Category,
    Customer,
    Order,
    OrderItem,
    Product,
    ProductImage,
)


class Command(BaseCommand):
    help = "Download Flipkart CSV, import products, create fake customers/orders, and sync data to Redis OM."

    def add_arguments(self, parser):
        parser.add_argument("--customers", type=int, default=5000)
        parser.add_argument("--orders", type=int, default=20000)
        parser.add_argument("--clear", action="store_true")

    def handle(self, *args, **options):
        customer_count = options["customers"]
        order_count = options["orders"]
        should_clear = options["clear"]

        if should_clear:
            self.clear_existing_data()

        csv_path = self.download_csv()
        self.import_products(csv_path)
        self.create_fake_customers(customer_count)
        self.create_fake_orders(order_count)

        # self.sync_products_to_redis()
        # self.sync_customer_analytics_to_redis()
        # self.sync_product_analytics_to_redis()
        # self.sync_dashboard_summary_to_redis()

        self.stdout.write(self.style.SUCCESS("Demo data load completed successfully."))

    # ---------------------------------------------------
    # STEP 1: DOWNLOAD CSV
    # ---------------------------------------------------
    def download_csv(self):
        tqdm.write("Downloading dataset from Kaggle...")
        path = kagglehub.dataset_download("atharvjairath/flipkart-ecommerce-dataset")
        tqdm.write(f"Dataset downloaded at: {path}")

        source_file = os.path.join(path, "flipkart_com-ecommerce_sample.csv")
        tqdm.write(f"Source file: {source_file}")

        if not os.path.exists(source_file):
            raise FileNotFoundError("flipkart_com-ecommerce_sample.csv not found!")

        public_dir = os.path.join(settings.BASE_DIR, "public")
        os.makedirs(public_dir, exist_ok=True)

        destination = os.path.join(public_dir, "flipkart_com-ecommerce_sample.csv")
        shutil.copy(source_file, destination)

        tqdm.write(f"CSV copied to: {destination}")
        return destination

    # ---------------------------------------------------
    # OPTIONAL: CLEAR OLD DATA
    # ---------------------------------------------------
    def clear_existing_data(self):
        tqdm.write("Clearing existing database data...")

        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        Customer.objects.all().delete()
        ProductImage.objects.all().delete()
        Product.objects.all().delete()
        Brand.objects.all().delete()
        Category.objects.all().delete()

        # tqdm.write("Clearing Redis OM data...")
        # self.clear_redis_model(ProductSearchCache)
        # self.clear_redis_model(CustomerAnalyticsCache)
        # self.clear_redis_model(ProductAnalyticsCache)

        tqdm.write("Existing data cleared.")

    def clear_redis_model(self, model_cls):
        try:
            pks = list(model_cls.all_pks())
            for pk in tqdm(pks, desc=f"Clearing {model_cls.__name__}", unit="records"):
                model_cls.delete(pk)
        except Exception as exc:
            self.stderr.write(f"Could not clear Redis model {model_cls.__name__}: {exc}")

    # ---------------------------------------------------
    # STEP 2: IMPORT PRODUCTS
    # ---------------------------------------------------
    def import_products(self, csv_path):
        tqdm.write("Importing products into database..." + str(csv_path))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = list(csv.DictReader(csvfile))
            for row in tqdm(reader, desc="Importing products into database", unit="records"):
                try:
                    with transaction.atomic():
                        product, created = self.create_or_update_product(row)
                        self.attach_categories(product, row.get("product_category_tree"))
                        self.attach_images(product, row.get("image"))
                except Exception as exc:
                    skipped_count += 1
                    tqdm.write(f"Skipping row: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Products imported. Created={created_count}, Updated={updated_count}, Skipped={skipped_count}"
            )
        )

    def create_or_update_product(self, row):
        pid = (row.get("pid") or "").strip()

        if not pid:
            raise ValueError("Missing pid")

        brand_name = (row.get("brand") or "").strip() or "Unknown"
        brand, _ = Brand.objects.get_or_create(name=brand_name[:100])

        defaults = {
            "pid": pid,
            "crawl_timestamp": self.parse_timestamp(row.get("crawl_timestamp")),
            "product_url": (row.get("product_url") or "").strip(),
            "name": (row.get("product_name") or "").strip()[:255],
            "description": (row.get("description") or "").strip(),
            "brand": brand,
            "retail_price": self.to_decimal(row.get("retail_price")),
            "discounted_price": self.to_decimal(row.get("discounted_price")),
            "product_rating": (row.get("product_rating") or "").strip()[:50],
            "overall_rating": (row.get("overall_rating") or "").strip()[:50],
            "is_fk_advantage_product": self.to_bool(row.get("is_FK_Advantage_product")),
            "product_specifications": self.parse_specifications(row.get("product_specifications")),
        }

        product, created = Product.objects.update_or_create(
            pid=pid,
            defaults=defaults,
        )
        return product, created

    def attach_categories(self, product, raw_tree):
        category_names = self.parse_category_tree(raw_tree)
        if not category_names:
            return

        categories = []
        for category_name in category_names:
            category, _ = Category.objects.get_or_create(name=category_name[:150])
            categories.append(category)

        product.categories.set(categories)

    def attach_images(self, product, raw_images):
        image_urls = self.parse_image_list(raw_images)
        if not image_urls:
            return

        existing_urls = set(product.images.values_list("image", flat=True))
        new_images = []

        for image_url in image_urls:
            if image_url and image_url not in existing_urls:
                new_images.append(ProductImage(product=product, image=image_url))

        if new_images:
            ProductImage.objects.bulk_create(new_images, batch_size=500)

    # ---------------------------------------------------
    # STEP 3: CREATE FAKE CUSTOMERS
    # ---------------------------------------------------
    def create_fake_customers(self, count):
        tqdm.write(f"Creating {count} fake customers...")

        if Customer.objects.exists():
            tqdm.write("Customers already exist. Skipping customer creation.")
            return

        fake = Faker()
        customers = []

        for _ in tqdm(range(count), desc="Preparing Customers", unit="customers"):
            customers.append(
                Customer(
                    full_name=fake.name(),
                    email=fake.unique.email(),
                    city=fake.city(),
                    country=fake.country(),
                )
            )

        Customer.objects.bulk_create(customers, batch_size=1000)
        self.stdout.write(self.style.SUCCESS(f"{count} customers created."))

    # ---------------------------------------------------
    # STEP 4: CREATE FAKE ORDERS
    # ---------------------------------------------------
    def create_fake_orders(self, count):
        tqdm.write(f"Creating {count} fake orders...")

        if Order.objects.exists():
            tqdm.write("Orders already exist. Skipping order creation.")
            return

        customers = list(Customer.objects.all().iterator(chunk_size=1000))
        products = list(Product.objects.all().iterator(chunk_size=1000))

        if not customers:
            raise ValueError("No customers found.")
        if not products:
            raise ValueError("No products found.")

        statuses = [
            Order.Status.PENDING,
            Order.Status.PAID,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
            Order.Status.CANCELED,
            Order.Status.REFUNDED,
        ]
        status_weights = [10, 20, 15, 40, 10, 5]
        payment_methods = ["card", "cash_on_delivery", "paypal", "bank_transfer", "upi"]

        now = timezone.now()
        orders_to_create = []
        order_items_payload = []

        for _ in tqdm(range(count), desc="Generating Orders", unit="orders"):
            customer = random.choice(customers)
            status = random.choices(statuses, weights=status_weights, k=1)[0]

            placed_at = now - timedelta(
                days=random.randint(0, 365),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            selected_products = random.sample(products, k=random.randint(1, 4))

            subtotal = Decimal("0.00")
            discount_amount = Decimal("0.00")
            shipping_cost = Decimal(str(random.choice([0, 40, 60, 80, 100])))
            item_payload = []

            for product in selected_products:
                base_price = (
                    product.discounted_price
                    if product.discounted_price > 0
                    else product.retail_price
                )

                if base_price <= 0:
                    base_price = Decimal(str(random.randint(100, 3000)))

                quantity = random.randint(1, 3)
                discount_per_unit = Decimal(
                    str(round(random.uniform(0, float(base_price) * 0.15), 2))
                )
                line_total = (base_price - discount_per_unit) * quantity

                if line_total < 0:
                    line_total = Decimal("0.00")

                subtotal += base_price * quantity
                discount_amount += discount_per_unit * quantity

                item_payload.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "unit_price": base_price,
                        "discount_per_unit": discount_per_unit,
                        "line_total": line_total.quantize(Decimal("0.01")),
                    }
                )

            taxable_amount = subtotal - discount_amount
            if taxable_amount < 0:
                taxable_amount = Decimal("0.00")

            tax_amount = (taxable_amount * Decimal("0.05")).quantize(Decimal("0.01"))
            total_amount = (taxable_amount + tax_amount + shipping_cost).quantize(Decimal("0.01"))

            paid_at = None
            delivered_at = None

            if status in [
                Order.Status.PAID,
                Order.Status.SHIPPED,
                Order.Status.DELIVERED,
                Order.Status.REFUNDED,
            ]:
                paid_at = placed_at + timedelta(hours=random.randint(1, 24))

            if status == Order.Status.DELIVERED:
                delivered_at = placed_at + timedelta(days=random.randint(2, 10))

            orders_to_create.append(
                Order(
                    customer=customer,
                    status=status,
                    subtotal=subtotal.quantize(Decimal("0.01")),
                    discount_amount=discount_amount.quantize(Decimal("0.01")),
                    shipping_cost=shipping_cost,
                    tax_amount=tax_amount,
                    total_amount=total_amount,
                    placed_at=placed_at,
                    paid_at=paid_at,
                    delivered_at=delivered_at,
                    payment_method=random.choice(payment_methods),
                    transaction_id=str(uuid.uuid4())[:20],
                )
            )
            order_items_payload.append(item_payload)

        tqdm.write("Saving orders to database...")
        created_orders = Order.objects.bulk_create(orders_to_create, batch_size=1000)

        tqdm.write("Preparing order items...")
        order_items = []

        for order, items in tqdm(
            zip(created_orders, order_items_payload),
            total=len(created_orders),
            desc="Building OrderItems",
            unit="orders",
        ):
            for item in items:
                order_items.append(
                    OrderItem(
                        order=order,
                        product=item["product"],
                        quantity=item["quantity"],
                        unit_price=item["unit_price"],
                        discount_per_unit=item["discount_per_unit"],
                        line_total=item["line_total"],
                    )
                )

        tqdm.write("Saving order items to database...")
        OrderItem.objects.bulk_create(order_items, batch_size=3000)
        self.stdout.write(self.style.SUCCESS(f"{count} orders created."))

    # ---------------------------------------------------
    # HELPERS
    # ---------------------------------------------------
    def parse_category_tree(self, raw_value):
        if not raw_value:
            return []

        try:
            parsed = ast.literal_eval(raw_value)
            if not parsed:
                return []

            first_path = parsed[0]
            return [part.strip() for part in first_path.split(">>") if part.strip()]
        except Exception:
            return []

    def parse_image_list(self, raw_value):
        if not raw_value:
            return []

        try:
            parsed = ast.literal_eval(raw_value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        return []

    def parse_specifications(self, raw_value):
        if not raw_value:
            return {}

        try:
            cleaned = raw_value.replace("=>", ":")
            parsed = ast.literal_eval(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        return {"raw": raw_value}

    def parse_timestamp(self, value):
        if not value:
            return None
        return parse_datetime(value)

    def to_decimal(self, value):
        if value in [None, "", "null"]:
            return Decimal("0.00")

        try:
            return Decimal(str(value).replace(",", "").strip())
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    def to_bool(self, value):
        return str(value).strip().lower() == "true"