from django.core.management.base import BaseCommand

from apps.inventory.tasks import scan_expiration_alerts


class Command(BaseCommand):
    help = "Détecte les produits expirés ou arrivant à expiration et notifie ADMIN."

    def handle(self, *args, **options):
        created = scan_expiration_alerts()
        self.stdout.write(self.style.SUCCESS(f"Scan d'expiration terminé ({created} alerte(s) créée(s))."))
