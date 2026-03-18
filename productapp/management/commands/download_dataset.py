from django.core.management.base import BaseCommand
import kagglehub


class Command(BaseCommand):
    help = "Download Amazon Fine Food Reviews dataset"

    def handle(self, *args, **kwargs):

        self.stdout.write("Downloading dataset from Kaggle...")

        path = kagglehub.dataset_download(
            "snap/amazon-fine-food-reviews"
        )

        self.stdout.write(
            self.style.SUCCESS(f"Dataset downloaded to: {path}")
        )