from django.db import models


class Product(models.Model):
    product_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.product_id


class Customer(models.Model):
    user_id = models.CharField(max_length=50, unique=True, db_index=True)
    profile_name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self) -> str:
        return self.user_id


class Review(models.Model):
    external_id = models.PositiveIntegerField(unique=True, db_index=True)
    help_numerator = models.PositiveIntegerField(default=0)
    help_denominator = models.PositiveIntegerField(default=0)
    score = models.DecimalField(max_digits=3, decimal_places=1)
    review_time = models.DateTimeField()
    summary = models.TextField(blank=True, null=True)
    text = models.TextField()

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="reviews",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["score"]),
            models.Index(fields=["review_time"]),
        ]
        ordering = ["-review_time"]

    def __str__(self) -> str:
        return f"Review {self.external_id} | {self.product.product_id}"
