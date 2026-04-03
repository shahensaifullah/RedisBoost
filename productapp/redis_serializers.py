from rest_framework import serializers


class ProductCacheSerializer(serializers.Serializer):
    django_id = serializers.IntegerField()
    pid = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    brand_name = serializers.CharField()
    primary_category = serializers.CharField()
    category_names = serializers.ListField(child=serializers.CharField(), default=list)
    image_urls = serializers.ListField(child=serializers.CharField(), default=list)
    retail_price = serializers.FloatField()
    discounted_price = serializers.FloatField()
    product_rating = serializers.CharField()
    overall_rating = serializers.CharField()
    is_fk_advantage_product = serializers.BooleanField()
    product_url = serializers.CharField()
    crawl_timestamp = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)