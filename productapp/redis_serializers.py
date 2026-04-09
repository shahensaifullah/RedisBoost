from rest_framework import serializers

class BrandCacheSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()

class CategoryCacheSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()

class ProductCacheSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='django_id')
    pid = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    brand = BrandCacheSerializer()
    categories = CategoryCacheSerializer(many=True)
    retail_price = serializers.FloatField()
    discounted_price = serializers.FloatField()
    product_rating = serializers.CharField()
    overall_rating = serializers.CharField()
    is_fk_advantage_product = serializers.BooleanField()
    crawl_timestamp = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    images = serializers.ListField(child=serializers.CharField(max_length=500), allow_null=True)
