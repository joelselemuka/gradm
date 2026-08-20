from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.inventory.models import InventoryCount, InventoryCountLine, StockLot, StockMovement
from apps.products.models import ProductVariant


@dataclass(frozen=True)
class Allocation:
    lot_id: int
    quantity: int


class InventoryService:
    @staticmethod
    def _stock_quantity(variant):
        return sum(variant.lots.values_list("quantity_available", flat=True))

    @staticmethod
    @transaction.atomic
    def start_count(*, actor, reference: str = "", note: str = ""):
        reference = reference.strip() or f"INV-{timezone.localdate():%Y%m%d}-{timezone.now().strftime('%H%M%S')}"
        if InventoryCount.objects.filter(reference=reference).exists():
            raise ValidationError("Cette référence d'inventaire existe déjà.")
        count = InventoryCount.objects.create(reference=reference, note=note.strip(), status=InventoryCount.Status.IN_PROGRESS, created_by=actor)
        variants = ProductVariant.objects.filter(active=True, product__active=True).prefetch_related("lots")
        InventoryCountLine.objects.bulk_create([
            InventoryCountLine(count=count, variant=variant, system_quantity=InventoryService._stock_quantity(variant))
            for variant in variants
        ])
        return count

    @staticmethod
    @transaction.atomic
    def set_count_line(*, line: InventoryCountLine, counted_quantity: int, note: str = ""):
        if line.count.status != InventoryCount.Status.IN_PROGRESS:
            raise ValidationError("Cet inventaire n'est plus modifiable.")
        if counted_quantity < 0:
            raise ValidationError("La quantité comptée ne peut pas être négative.")
        line.counted_quantity = counted_quantity
        line.difference = counted_quantity - line.system_quantity
        line.note = note.strip()
        line.counted_at = timezone.now()
        line.save(update_fields=["counted_quantity", "difference", "note", "counted_at"])
        return line

    @staticmethod
    @transaction.atomic
    def complete_count(*, count: InventoryCount, actor):
        count = InventoryCount.objects.select_for_update().get(pk=count.pk)
        if count.status != InventoryCount.Status.IN_PROGRESS:
            raise ValidationError("Cet inventaire est déjà clôturé ou annulé.")
        lines = list(count.lines.select_related("variant").select_for_update())
        if any(line.counted_quantity is None for line in lines):
            raise ValidationError("Saisissez toutes les quantités comptées avant de clôturer l'inventaire.")
        for line in lines:
            delta = line.counted_quantity - line.system_quantity
            if not delta:
                continue
            lots = list(StockLot.objects.select_for_update().filter(variant=line.variant).order_by("expires_at", "received_at", "pk"))
            if delta > 0:
                # Utiliser le coût moyen des lots existants pour ne pas fausser la valeur du stock.
                # Si aucun lot n'existe, le coût reste à 0 (à corriger manuellement si nécessaire).
                from django.db.models import Avg
                avg_cost = StockLot.objects.filter(
                    variant=line.variant, quantity_available__gt=0
                ).aggregate(avg=Avg("unit_cost"))["avg"] or Decimal("0.00")
                lot = lots[0] if lots else StockLot.objects.create(variant=line.variant, code=f"INVENTORY-{count.reference}-{line.variant_id}", unit_cost=avg_cost, quantity_available=0)
                lot.quantity_available += delta
                lot.save(update_fields=["quantity_available"])
                StockMovement.objects.create(lot=lot, movement_type=StockMovement.Type.ADJUSTMENT, quantity_delta=delta, reference=count.reference, note="Inventaire physique", actor=actor)
            else:
                remaining = -delta
                for lot in lots:
                    taken = min(lot.quantity_available, remaining)
                    if not taken:
                        continue
                    lot.quantity_available -= taken
                    lot.save(update_fields=["quantity_available"])
                    StockMovement.objects.create(lot=lot, movement_type=StockMovement.Type.ADJUSTMENT, quantity_delta=-taken, reference=count.reference, note="Inventaire physique", actor=actor)
                    remaining -= taken
                    if remaining == 0:
                        break
                if remaining:
                    raise ValidationError(f"Stock incohérent pour {line.variant}.")
        count.status = InventoryCount.Status.COMPLETED
        count.completed_at = timezone.now()
        count.completed_by = actor
        count.save(update_fields=["status", "completed_at", "completed_by"])
        return count

    @staticmethod
    @transaction.atomic
    def receive_batch(*, lines, actor, reference: str):
        if not reference.strip():
            raise ValidationError("La référence de réception est obligatoire.")
        if not lines:
            raise ValidationError("Ajoutez au moins un article à réceptionner.")
        received = []
        for line in lines:
            received.append(InventoryService.receive(variant=line["variant"], lot_code=line.get("lot_code") or f"{reference}-{line['variant'].pk}", quantity=line["quantity"], unit_cost=line.get("unit_cost", Decimal("0.00")), actor=actor, expires_at=line.get("expires_at"), reference=reference))
        return received

    @staticmethod
    @transaction.atomic
    def issue_batch(*, lines, actor, reference: str, reason: str):
        if not reference.strip():
            raise ValidationError("La référence de sortie est obligatoire.")
        if not reason.strip():
            raise ValidationError("Le motif global de sortie est obligatoire.")
        if not lines:
            raise ValidationError("Ajoutez au moins un article à sortir.")
        for line in lines:
            InventoryService.issue(variant=line["variant"], quantity=line["quantity"], actor=actor, reason=reason, reference=reference)

    @staticmethod
    @transaction.atomic
    def receive(*, variant: ProductVariant, lot_code: str, quantity: int, unit_cost, actor, expires_at: date | None = None, reference: str):
        if quantity <= 0:
            raise ValidationError("La quantité reçue doit être positive.")
        if variant.product.expiration_managed:
            expires_at = expires_at or variant.product.expiration_date
            if expires_at is None:
                raise ValidationError("Une date d’expiration est obligatoire pour ce produit.")
        lot, _ = StockLot.objects.select_for_update().get_or_create(
            variant=variant, code=lot_code,
            defaults={"expires_at": expires_at, "unit_cost": unit_cost, "quantity_available": 0},
        )
        if lot.expires_at != expires_at and lot.quantity_available:
            raise ValidationError("Un lot existant ne peut pas changer de date d'expiration.")
        lot.quantity_available += quantity
        lot.unit_cost = unit_cost
        lot.save(update_fields=["quantity_available", "unit_cost"])
        StockMovement.objects.create(lot=lot, movement_type=StockMovement.Type.RECEIPT, quantity_delta=quantity, reference=reference, actor=actor)
        from apps.purchases.replenishment import ReplenishmentService
        ReplenishmentService.evaluate_variant(variant=variant)
        return lot

    @staticmethod
    @transaction.atomic
    def allocate_fefo(*, variant: ProductVariant, quantity: int, actor, reference: str):
        if quantity <= 0:
            raise ValidationError("La quantité vendue doit être positive.")
        lots = list(StockLot.objects.select_for_update().sellable().filter(variant=variant).order_by("expires_at", "received_at", "pk"))
        remaining = quantity
        allocations = []
        for lot in lots:
            taken = min(lot.quantity_available, remaining)
            if not taken: continue
            lot.quantity_available -= taken
            lot.save(update_fields=["quantity_available"])
            StockMovement.objects.create(lot=lot, movement_type=StockMovement.Type.SALE, quantity_delta=-taken, reference=reference, actor=actor)
            allocations.append(Allocation(lot_id=lot.pk, quantity=taken))
            remaining -= taken
            if remaining == 0: break
        if remaining:
            raise ValidationError("Stock disponible insuffisant.")
        from apps.purchases.replenishment import ReplenishmentService
        ReplenishmentService.evaluate_variant(variant=variant)
        return allocations

    @staticmethod
    @transaction.atomic
    def issue(*, variant: ProductVariant, quantity: int, actor, reason: str, reference: str):
        if quantity <= 0:
            raise ValidationError("La quantité de sortie doit être positive.")
        if not reason.strip():
            raise ValidationError("Un motif de sortie est obligatoire.")
        lots = list(StockLot.objects.select_for_update().sellable().filter(variant=variant).order_by("expires_at", "received_at", "pk"))
        remaining = quantity
        for lot in lots:
            taken = min(lot.quantity_available, remaining)
            if not taken:
                continue
            lot.quantity_available -= taken
            lot.save(update_fields=["quantity_available"])
            StockMovement.objects.create(lot=lot, movement_type=StockMovement.Type.STOCK_OUT, quantity_delta=-taken, reference=reference, actor=actor, note=reason.strip())
            remaining -= taken
            if remaining == 0:
                break
        if remaining:
            raise ValidationError("Stock disponible insuffisant pour cette sortie.")
        from apps.purchases.replenishment import ReplenishmentService
        ReplenishmentService.evaluate_variant(variant=variant)
