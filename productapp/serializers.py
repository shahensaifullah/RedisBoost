from rest_framework import serializers


class BrandSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()

class CategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()

class ProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    pid = serializers.CharField()
    crawl_timestamp = serializers.DateTimeField(allow_null=True)
    name = serializers.CharField()
    description = serializers.CharField()
    brand = BrandSerializer()
    categories = CategorySerializer(many=True)
    retail_price = serializers.FloatField()
    discounted_price = serializers.FloatField()
    product_rating = serializers.CharField()
    overall_rating = serializers.CharField()
    is_fk_advantage_product = serializers.BooleanField()
    images = serializers.SerializerMethodField()

    created_at = serializers.DateTimeField(allow_null=True)

    def get_images(self, obj):
        return obj.images.all().values_list('image', flat=True)