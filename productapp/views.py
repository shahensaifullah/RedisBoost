from django.db.models import QuerySet
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from .models import Product
from .pagination import ProductPagination
from .redis_models import ProductCache
from .redis_serializers import ProductCacheSerializer
from .serializers import ProductSerializer
from .tasks import cache_all_products_task

class ProductListView(ListAPIView):
    pagination_class = ProductPagination

    def get_queryset(self) -> QuerySet[Product]:
        return (
            Product.objects
            .select_related("brand")
            .prefetch_related("categories", "images")
            .order_by("id")
        )

    def _redis_has_data(self) -> bool:
        try:
            return ProductCache.find().count() > 0
        except Exception:
            return False

    def _get_redis_results(self):
        """
        Returns all cached Redis products as plain dict-like objects.
        For larger systems, move filtering/sorting/pagination deeper into Redis query.
        """
        try:
            cached_docs = list(ProductCache.find())
            print("Redis results: ", cached_docs)
            return cached_docs
        except Exception as e:
            print(e)
            return []

    def list(self, request, *args, **kwargs):
        use_cache = self._redis_has_data()

        if use_cache:
            print("use_cache: ", use_cache)
            redis_results = self._get_redis_results()
            page = self.paginate_queryset(redis_results)
            serializer = ProductCacheSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response["X-Data-Source"] = "redis"
            return response

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = ProductSerializer(page, many=True)

        try:
            cache_all_products_task.delay()
        except Exception:
            pass

        response = self.get_paginated_response(serializer.data)
        response["X-Data-Source"] = "database"
        response["X-Cache-Backfill"] = "started"
        return response