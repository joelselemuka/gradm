from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from apps.audit.services import audit
from apps.inventory.services import InventoryService
from .models import PurchaseOrder


class PurchaseService:
    @staticmethod
    @transaction.atomic
    def receive_line(*, order, line, quantity, lot_code, expires_at, actor):
        if not actor.can_manage_inventory(): raise PermissionDenied("Réception non autorisée.")
        order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if order.status in {PurchaseOrder.Status.CANCELLED, PurchaseOrder.Status.RECEIVED}: raise ValidationError("Commande non réceptionnable.")
        line = order.lines.select_for_update().get(pk=line.pk)
        if quantity <= 0 or line.received_quantity + quantity > line.ordered_quantity: raise ValidationError("Quantité reçue invalide.")
        lot = InventoryService.receive(variant=line.variant, lot_code=lot_code, quantity=quantity, unit_cost=line.unit_cost, actor=actor, expires_at=expires_at, reference=order.reference)
        line.received_quantity += quantity; line.save(update_fields=["received_quantity"])
        if order.paid_in_cash:
            if not order.cash_session: raise ValidationError("Une session de caisse est obligatoire pour cet achat espèces.")
            from apps.pos.models import CashTransaction
            from apps.pos.services import CashSessionService
            CashSessionService.record_movement(session=order.cash_session, actor=actor, direction=CashTransaction.Direction.OUT, category=CashTransaction.Category.PURCHASE, amount=line.unit_cost * quantity, description=f"Réception {order.reference}", reference=order.reference)
        lines = order.lines.all()
        order.status = PurchaseOrder.Status.RECEIVED if all(row.received_quantity == row.ordered_quantity for row in lines) else PurchaseOrder.Status.PARTIAL
        order.save(update_fields=["status"]); audit(actor=actor, action="PURCHASE_RECEIVED", target=order, after={"line": line.pk, "quantity": quantity})
        return lot
