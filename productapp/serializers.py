from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    category_names = serializers.SerializerMethodField()
    image_urls = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "pid",
            "name",
            "description",
            "brand_name",
            "retail_price",
            "discounted_price",
            "product_rating",
            "overall_rating",
            "is_fk_advantage_product",
            "category_names",
            "image_urls",
            "product_url",
            "crawl_timestamp",
            "created_at",
        ]

    def get_category_names(self, obj):
        return list(obj.categories.values_list("name", flat=True))

    def get_image_urls(self, obj):
        return list(obj.images.values_list("image", flat=True))