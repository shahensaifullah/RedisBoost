from django.apps import AppConfig

from productapp.redis_models import run_redis_migrations


class ProductappConfig(AppConfig):
    name = 'productapp'

    def ready(self):
        run_redis_migrations()