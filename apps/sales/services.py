from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.audit.services import audit
from apps.inventory.models import StockLot, StockMovement
from apps.inventory.services import InventoryService
from apps.sales.models import Invoice, InvoiceLine, Payment


MONEY = Decimal("0.01")


@dataclass(frozen=True)
class SaleItem:
    variant_id: int
    quantity: int


class SaleService:
    @staticmethod
    def generate_invoice_number():
        """Generate a readable daily invoice identifier with a collision-safe suffix."""
        prefix = f"FAC-{timezone.localdate():%Y%m%d}-"
        while True:
            number = f"{prefix}{uuid4().hex[:6].upper()}"
            if not Invoice.objects.filter(number=number).exists():
                return number

    @staticmethod
    def quote_sale(*, items: list[SaleItem], manual_discount: Decimal = Decimal("0")):
        """Calculate a non-persistent preview. Final stock checks happen at validation."""
        if not items:
            raise ValidationError("Le panier est vide.")
        from apps.products.models import ProductVariant
        quantities = {}
        for item in items:
            if item.quantity <= 0:
                raise ValidationError("La quantité doit être positive.")
            quantities[item.variant_id] = quantities.get(item.variant_id, 0) + item.quantity
        variants = {variant.pk: variant for variant in ProductVariant.objects.select_related("product").filter(pk__in=quantities, active=True, product__active=True)}
        if len(variants) != len(quantities):
            raise ValidationError("Un article est indisponible.")
        lines, subtotal, promotion_discount = [], Decimal("0"), Decimal("0")
        from apps.promotions.services import DiscountService
        for variant_id, quantity in quantities.items():
            variant = variants[variant_id]
            discount, _ = DiscountService.promotion_discount(variant=variant, quantity=quantity, unit_price=variant.sale_price)
            line_total = (variant.sale_price * quantity - discount).quantize(MONEY, rounding=ROUND_HALF_UP)
            lines.append({"variant": variant, "quantity": quantity, "unit_price": variant.sale_price, "promotion_discount": discount, "line_total": line_total})
            subtotal += line_total
            promotion_discount += discount
        subtotal = subtotal.quantize(MONEY)
        order_discount, _ = DiscountService.configured_order_discount(subtotal=subtotal)
        promotion_discount = (promotion_discount + order_discount).quantize(MONEY)
        manual_discount = DiscountService.validate_manual_discount(amount=manual_discount, subtotal=subtotal - order_discount)
        return {"lines": lines, "subtotal": subtotal, "promotion_discount": promotion_discount, "manual_discount": manual_discount, "total": (subtotal - promotion_discount - manual_discount).quantize(MONEY)}

    @staticmethod
    @transaction.atomic
    def create_sale(*, actor, items: list[SaleItem], payment_method: str, cash_received: Decimal | None = None, customer=None, customer_name: str = "", customer_phone: str = "", manual_discount: Decimal = Decimal("0"), cash_session=None, invoice_number: str | None = None):
        if not actor.can_operate_pos():
            raise PermissionDenied("Cet utilisateur ne peut pas encaisser.")
        quote = SaleService.quote_sale(items=items, manual_discount=manual_discount)
        from apps.products.models import ProductVariant
        quantities = {}
        for item in items:
            if item.quantity <= 0:
                raise ValidationError("La quantité doit être positive.")
            quantities[item.variant_id] = quantities.get(item.variant_id, 0) + item.quantity
        variants = {v.pk: v for v in ProductVariant.objects.select_related("product").filter(pk__in=quantities, active=True, product__active=True)}
        if len(variants) != len(quantities):
            raise ValidationError("Un article est indisponible.")
        if cash_session is None:
            from apps.pos.models import CashSession
            cash_session = CashSession.objects.select_for_update().filter(cashier=actor, status=CashSession.Status.OPEN).first()
        if cash_session is None or cash_session.status != cash_session.Status.OPEN:
            raise ValidationError("Une session de caisse ouverte est obligatoire pour encaisser.")
        if cash_session.cashier_id != actor.pk:
            raise PermissionDenied("La session de caisse doit appartenir au caissier.")
        number = invoice_number or SaleService.generate_invoice_number()
        invoice = Invoice.objects.create(number=number, cashier=actor, cash_session=cash_session, customer=customer, customer_name=(customer.name if customer else customer_name.strip()), customer_phone=customer_phone.strip(), subtotal=Decimal("0"), total=Decimal("0"))
        subtotal = Decimal("0")
        promotion_discount = Decimal("0")
        for variant_id, quantity in quantities.items():
            variant = variants[variant_id]
            from apps.promotions.services import DiscountService
            discount, _ = DiscountService.promotion_discount(variant=variant, quantity=quantity, unit_price=variant.sale_price)
            line_total = (variant.sale_price * quantity - discount).quantize(MONEY, rounding=ROUND_HALF_UP)
            InvoiceLine.objects.create(invoice=invoice, variant=variant, product_name=variant.product.name, variant_name=variant.name, barcode=variant.barcode or "", quantity=quantity, unit_price=variant.sale_price, promotion_discount=discount, line_total=line_total)
            InventoryService.allocate_fefo(variant=variant, quantity=quantity, actor=actor, reference=invoice.number)
            subtotal += line_total
            promotion_discount += discount
        subtotal = subtotal.quantize(MONEY)
        order_discount, _ = DiscountService.configured_order_discount(subtotal=subtotal)
        promotion_discount = (promotion_discount + order_discount).quantize(MONEY)
        manual_discount = DiscountService.validate_manual_discount(amount=manual_discount, subtotal=subtotal - order_discount)
        invoice.subtotal = subtotal
        invoice.promotion_discount = promotion_discount
        invoice.manual_discount = manual_discount
        invoice.total = (subtotal - promotion_discount - manual_discount).quantize(MONEY)
        invoice.save(update_fields=["subtotal", "promotion_discount", "manual_discount", "total"])
        if payment_method == Payment.Method.CASH:
            if cash_received is None or cash_received < invoice.total:
                raise ValidationError("Le montant reçu est inférieur au total.")
            change_due = (cash_received - invoice.total).quantize(MONEY)
        else:
            cash_received, change_due = None, Decimal("0")
        Payment.objects.create(invoice=invoice, method=payment_method, amount=invoice.total, cash_received=cash_received, change_due=change_due)
        audit(actor=actor, action="SALE_VALIDATED", target=invoice, after={"total": str(invoice.total)})
        return invoice


class InvoiceService:
    @staticmethod
    @transaction.atomic
    def cancel_invoice(*, invoice: Invoice, actor, reason: str):
        if not actor.can_cancel_invoice():
            raise PermissionDenied("Seul un administrateur peut annuler une facture.")
        if not reason.strip():
            raise ValidationError("Un motif d'annulation est obligatoire.")
        invoice = Invoice.objects.select_for_update().select_related("cash_session").get(pk=invoice.pk)
        if invoice.status == Invoice.Status.CANCELLED:
            raise ValidationError("Cette facture est déjà annulée.")
        # ☹️ Garde critique : session clôturée → données figées, annulation interdite
        if invoice.cash_session and invoice.cash_session.status != invoice.cash_session.Status.OPEN:
            raise ValidationError(
                "Impossible d'annuler une facture appartenant à une session clôturée. "
                "Le rapport de cette session est définitif."
            )
        if invoice.created_at.date() != timezone.localdate():
            raise ValidationError("Seules les factures émises aujourd'hui peuvent être annulées.")
        for line in invoice.lines.select_related("variant").all():
            movements = StockMovement.objects.select_related("lot").filter(reference=invoice.number, movement_type=StockMovement.Type.SALE, lot__variant=line.variant)
            for movement in movements:
                lot = StockLot.objects.select_for_update().get(pk=movement.lot_id)
                quantity = -movement.quantity_delta
                lot.quantity_available += quantity
                lot.save(update_fields=["quantity_available"])
                StockMovement.objects.create(lot=lot, movement_type=StockMovement.Type.SALE_CANCELLED, quantity_delta=quantity, reference=invoice.number, actor=actor, note=reason)
        invoice.status = Invoice.Status.CANCELLED
        invoice.cancelled_by = actor
        invoice.cancelled_at = timezone.now()
        invoice.cancellation_reason = reason
        invoice.save(update_fields=["status", "cancelled_by", "cancelled_at", "cancellation_reason"])
        audit(actor=actor, action="INVOICE_CANCELLED", target=invoice, after={"reason": reason})
        return invoice
