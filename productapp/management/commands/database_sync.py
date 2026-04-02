import os
import shutil

import kagglehub
from django.conf import settings
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = "Download Reviews.csv from Kaggle Hub, migrate, and import into database"

    def handle(self, *args, **options):
        path = kagglehub.dataset_download("atharvjairath/flipkart-ecommerce-dataset")
        self.stdout.write(f"Dataset downloaded at: {path}")

        source_file = os.path.join(path, "flipkart_com-ecommerce_sample.csv")
        self.stdout.write(f"Source file: {source_file}")
        if not os.path.exists(source_file):
            self.stderr.write("flipkart_com-ecommerce_sample.csv not found!")
            return

        public_dir = os.path.join(settings.BASE_DIR, "public")
        os.makedirs(public_dir, exist_ok=True)
        destination = os.path.join(public_dir, "flipkart_com-ecommerce_sample.csv")
        shutil.copy(source_file, destination)

