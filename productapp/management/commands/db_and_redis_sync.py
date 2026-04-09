import ast
import csv
import os
import random
import secrets
import shutil
import string
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import kagglehub
from django.conf import settings
from django.core.management import BaseCommand, call_command
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
    help = "Download dataset, save to database and from database, save to redis"


    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Running makemigrations..."))
        call_command("makemigrations")

        self.stdout.write(self.style.WARNING("Running migrate..."))
        call_command("migrate")

        self.stdout.write(self.style.WARNING("Running download dataset..."))
        call_command("download_dataset")

        self.stdout.write(self.style.WARNING("Running download sync with redis..."))
        call_command("sync_db_to_redis")

