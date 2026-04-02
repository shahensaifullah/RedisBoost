import csv
import hashlib
import os
import shutil
from datetime import datetime, timezone
from decimal import Decimal

import kagglehub
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

from productapp.models import Product, Customer, Review
from productapp.redi_models import (
    ProductCache,
    CustomerCache,
    ReviewCache,
    run_redis_migrations,
)

fake = Faker()


ADJECTIVES = [
        "Organic", "Premium", "Classic", "Natural", "Fresh", "Deluxe", "Healthy", "Golden",
        "Signature", "Pure", "Savory", "Rich", "Authentic", "Traditional", "Crafted",
        "Farmhouse", "Artisan", "Select", "Superior", "Wholesome"
    ]

FLAVORS = [
        "Vanilla", "Chocolate", "Honey", "Roasted", "Salted", "Sweet", "Berry", "Lemon",
        "Herbal", "Caramel", "Coconut", "Almond", "Hazelnut", "Strawberry", "Apple",
        "Cinnamon", "Peppermint", "Maple", "Mocha", "Banana"
    ]

PRODUCT_TYPES = [
        "Tea", "Coffee", "Snack Bar", "Protein Bar", "Cookies", "Biscuits",
        "Chocolate", "Granola", "Cereal", "Energy Bites", "Protein Mix",
        "Honey Spread", "Nut Mix", "Trail Mix", "Spice Blend", "Green Tea",
        "Black Tea", "Herbal Tea", "Instant Coffee", "Ground Coffee",
        "Energy Drink", "Fruit Juice", "Smoothie Mix", "Oatmeal", "Pancake Mix",
        "Peanut Butter", "Almond Butter", "Protein Shake", "Vitamin Gummies"
    ]


def generate_product_name(product_id):
    digest = hashlib.md5(product_id.encode()).hexdigest()

    adj = ADJECTIVES[int(digest[0:2], 16) % len(ADJECTIVES)]
    flavor = FLAVORS[int(digest[2:4], 16) % len(FLAVORS)]
    ptype = PRODUCT_TYPES[int(digest[4:6], 16) % len(PRODUCT_TYPES)]

    return f"{adj} {flavor} {ptype}"

class Command(BaseCommand):
    help = "Download Reviews.csv from Kaggle Hub, migrate, and import into database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Batch size for bulk insert",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional limit for testing import",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        limit = options["limit"]

        self.stdout.write("Downloading dataset from Kaggle...")

        dataset_path = kagglehub.dataset_download("snap/amazon-fine-food-reviews")
        self.stdout.write(f"Dataset downloaded at: {dataset_path}")

        source_file = os.path.join(dataset_path, "Reviews.csv")
        if not os.path.exists(source_file):
            self.stderr.write("Reviews.csv not found!")
            return

        public_dir = os.path.join(settings.BASE_DIR, "public")
        os.makedirs(public_dir, exist_ok=True)

        destination = os.path.join(public_dir, "Reviews.csv")
        shutil.copy(source_file, destination)

        self.stdout.write(
            self.style.SUCCESS(f"Reviews.csv saved to {destination}")
        )

        self.stdout.write(self.style.WARNING("Running makemigrations..."))
        call_command("makemigrations")

        self.stdout.write(self.style.WARNING("Running migrate..."))
        call_command("migrate")

        self.stdout.write(self.style.WARNING("Starting CSV import..."))
        self.import_reviews(destination, batch_size=batch_size, limit=limit)

        self.stdout.write(self.style.WARNING("Running Redis OM migrations..."))
        run_redis_migrations()






    def import_reviews(self, file_path, batch_size=5000, limit=None):
        rows_processed = 0
        total_products_created = 0
        total_customers_created = 0
        total_reviews_created = 0

        with open(file_path, "r", encoding="utf-8", newline="") as csvfile:
            reader = csv.DictReader(csvfile)

            product_buffer = {}
            customer_buffer = {}
            review_buffer = []

            for row in reader:
                if limit and rows_processed >= limit:
                    break

                try:
                    external_id = int(row["Id"])
                    product_id = (row["ProductId"] or "").strip()
                    user_id = (row["UserId"] or "").strip()
                    profile_name = (row.get("ProfileName") or "").strip() or None
                    help_numerator = int(row.get("HelpfulnessNumerator") or 0)
                    help_denominator = int(row.get("HelpfulnessDenominator") or 0)
                    score = Decimal(str(row["Score"]))
                    review_time = datetime.fromtimestamp(
                        int(row["Time"]),
                        tz=timezone.utc,
                    )
                    summary = (row.get("Summary") or "").strip() or None
                    text = (row.get("Text") or "").strip()

                    if not product_id or not user_id or not text:
                        continue

                    if product_id not in product_buffer:
                        product_buffer[product_id] = Product(
                            product_id=product_id,
                            name=generate_product_name(product_id)
                        )

                    if user_id not in customer_buffer:
                        customer_buffer[user_id] = Customer(
                            user_id=user_id,
                            profile_name=profile_name,
                        )

                    review_buffer.append(
                        {
                            "external_id": external_id,
                            "product_id": product_id,
                            "user_id": user_id,
                            "help_numerator": help_numerator,
                            "help_denominator": help_denominator,
                            "score": score,
                            "review_time": review_time,
                            "summary": summary,
                            "text": text,
                        }
                    )

                    rows_processed += 1

                    if len(review_buffer) >= batch_size:
                        p, c, r = self.flush_batch(
                            product_buffer,
                            customer_buffer,
                            review_buffer,
                            batch_size,
                        )
                        total_products_created += p
                        total_customers_created += c
                        total_reviews_created += r

                        self.stdout.write(
                            f"Processed={rows_processed} | "
                            f"Products={total_products_created} | "
                            f"Customers={total_customers_created} | "
                            f"Reviews={total_reviews_created}"
                        )

                        product_buffer.clear()
                        customer_buffer.clear()
                        review_buffer.clear()

                except Exception as e:
                    self.stderr.write(
                        f"Skipping row around {rows_processed + 1}: {e}"
                    )

            if review_buffer:
                p, c, r = self.flush_batch(
                    product_buffer,
                    customer_buffer,
                    review_buffer,
                    batch_size,
                )
                total_products_created += p
                total_customers_created += c
                total_reviews_created += r

        self.stdout.write(
            self.style.SUCCESS(
                f"Import finished. "
                f"Rows processed={rows_processed}, "
                f"Products created={total_products_created}, "
                f"Customers created={total_customers_created}, "
                f"Reviews created={total_reviews_created}"
            )
        )

    def save_to_redis(self, products, customers, reviews):
        for item in products:
            try:
                item.save()
            except Exception as e:
                self.stderr.write(f"Redis product save failed: {e}")

        for item in customers:
            try:
                item.save()
            except Exception as e:
                self.stderr.write(f"Redis customer save failed: {e}")

        for item in reviews:
            try:
                item.save()
            except Exception as e:
                self.stderr.write(f"Redis review save failed: {e}")
                

    @transaction.atomic
    def flush_batch(self, product_buffer, customer_buffer, review_buffer, batch_size):
        product_ids = list(product_buffer.keys())
        user_ids = list(customer_buffer.keys())
        external_ids = [item["external_id"] for item in review_buffer]

        existing_product_ids = set(
            Product.objects.filter(product_id__in=product_ids)
            .values_list("product_id", flat=True)
        )
        existing_user_ids = set(
            Customer.objects.filter(user_id__in=user_ids)
            .values_list("user_id", flat=True)
        )
        existing_review_ids = set(
            Review.objects.filter(external_id__in=external_ids)
            .values_list("external_id", flat=True)
        )

        new_products = [
            product_buffer[pid]
            for pid in product_ids
            if pid not in existing_product_ids
        ]
        new_customers = [
            customer_buffer[uid]
            for uid in user_ids
            if uid not in existing_user_ids
        ]

        Product.objects.bulk_create(
            new_products,
            batch_size=batch_size,
            ignore_conflicts=True,
        )
        Customer.objects.bulk_create(
            new_customers,
            batch_size=batch_size,
            ignore_conflicts=True,
        )

        product_map = {
            obj.product_id: obj
            for obj in Product.objects.filter(product_id__in=product_ids)
        }
        customer_map = {
            obj.user_id: obj
            for obj in Customer.objects.filter(user_id__in=user_ids)
        }

        new_reviews = []
        redis_products_to_save = []
        redis_customers_to_save = []
        redis_reviews_to_save = []

        for product in new_products:
            redis_products_to_save.append(
                ProductCache(
                    product_id=product.product_id,
                    name=product.name,
                )
            )

        for customer in new_customers:
            redis_customers_to_save.append(
                CustomerCache(
                    user_id=customer.user_id,
                    profile_name=customer.profile_name,
                )
            )

        for item in review_buffer:
            if item["external_id"] in existing_review_ids:
                continue

            product = product_map.get(item["product_id"])
            customer = customer_map.get(item["user_id"])

            if not product or not customer:
                continue

            review = Review(
                external_id=item["external_id"],
                help_numerator=item["help_numerator"],
                help_denominator=item["help_denominator"],
                score=item["score"],
                review_time=item["review_time"],
                summary=item["summary"],
                text=item["text"],
                product=product,
                customer=customer,
            )
            new_reviews.append(review)

            redis_reviews_to_save.append(
                ReviewCache(
                    external_id=item["external_id"],
                    help_numerator=item["help_numerator"],
                    help_denominator=item["help_denominator"],
                    score=float(item["score"]),
                    review_time=item["review_time"],
                    summary=item["summary"],
                    text=item["text"],
                    product_id=product.product_id,
                    product_name=product.name,
                    user_id=customer.user_id,
                    profile_name=customer.profile_name,
                )
            )

        Review.objects.bulk_create(
            new_reviews,
            batch_size=batch_size,
            ignore_conflicts=True,
        )

        self.save_to_redis(
            products=redis_products_to_save,
            customers=redis_customers_to_save,
            reviews=redis_reviews_to_save,
        )

        return len(new_products), len(new_customers), len(new_reviews)