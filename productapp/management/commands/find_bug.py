
from django.core.management.base import BaseCommand
from redis_om import RedisModel

from productapp.redis_models import ProductCache


class Command(BaseCommand):

    def handle(self, *args, **options):
        ProductCache.find(pid=1)
