from django.core.management.base import BaseCommand
from ledger.models import Service

DEFAULT_SERVICES = [
    ("Photocopying", 5),
    ("Printing (B&W)", 10),
    ("Printing (Color)", 20),
    ("Scanning", 10),
    ("Lamination", 30),
    ("Typing / Document creation", 50),
    ("Internet browsing", 1),
    ("Binding", 100),
    ("Passport photo", 100),
]


class Command(BaseCommand):
    help = "Seed the default Nebissi services if none exist."

    def handle(self, *args, **options):
        created = 0
        for name, price in DEFAULT_SERVICES:
            obj, was_created = Service.objects.get_or_create(name=name, defaults={"default_price": price})
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new service(s). {Service.objects.count()} total."))
