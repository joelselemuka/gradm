from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="audit_entries")
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    # ── Affichage lisible ──────────────────────────────────────────────────────

    _TYPE_LABELS = {
        "accounts.User":            "Utilisateur",
        "pos.CashSession":          "Session caisse",
        "pos.CashRegister":         "Caisse",
        "pos.CashTransaction":      "Mouvement cash",
        "sales.Invoice":            "Facture",
        "sales.Payment":            "Paiement",
        "expenses.Expense":         "Dépense",
        "products.Product":         "Produit",
        "products.ProductVariant":  "Variante produit",
        "inventory.InventoryCount": "Inventaire",
        "inventory.StockLot":       "Lot de stock",
        "purchases.PurchaseOrder":  "Bon de commande",
    }

    @property
    def target_label(self):
        """Nom lisible du modèle cible, ex. 'Facture #42'."""
        label = self._TYPE_LABELS.get(
            self.target_type,
            self.target_type.split(".")[-1] if "." in self.target_type else self.target_type,
        )
        return f"{label} #{self.target_id}"

    @property
    def formatted_after(self):
        """Résumé lisible du champ `after` (JSON → clé: valeur)."""
        if not self.after or not isinstance(self.after, dict):
            return str(self.after) if self.after else "—"
        parts = []
        for k, v in self.after.items():
            if v is None:
                continue
            v_str = str(v)[:60] + ("…" if len(str(v)) > 60 else "")
            parts.append(f"{k}: {v_str}")
        return " · ".join(parts[:5]) or "—"
