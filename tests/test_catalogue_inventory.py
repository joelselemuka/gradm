from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.inventory.models import InventoryCount, StockLot, StockMovement
from apps.inventory.services import InventoryService
from apps.products.models import Category, Product, ProductBarcode, ProductVariant
from apps.products.services import ProductBarcodeService


class BarcodeAndInventoryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("catalogue-admin", password="test", role=User.Role.ADMIN)
        category = Category.objects.create(name="Tests")
        product = Product.objects.create(name="Article test", internal_reference="TEST-001", category=category)
        self.variant = ProductVariant.objects.create(product=product, name="Unité", sku="TEST-SKU", sale_price=Decimal("1250"), purchase_price=Decimal("0"))

    def test_aliases_are_unique_and_internal_code_is_ean13(self):
        alias = ProductBarcodeService.ensure_internal_code(self.variant, actor=self.admin)
        self.assertEqual(len(alias.code), 13)
        self.assertTrue(alias.code.isdigit())
        self.assertEqual(ProductBarcodeService.ensure_internal_code(self.variant).pk, alias.pk)
        other = ProductVariant.objects.create(product=self.variant.product, name="Deux", sku="TEST-SKU-2", sale_price=1, purchase_price=0)
        with self.assertRaises(ValidationError):
            ProductBarcodeService.add_alias(other, alias.code, ProductBarcode.Kind.SUPPLIER)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/products/{self.variant.product_id}/variants/{self.variant.pk}/barcodes/print/").status_code, 200)
        self.assertEqual(self.client.get("/products/labels/print/").status_code, 200)

    def test_inventory_count_applies_physical_difference_as_adjustment(self):
        InventoryService.receive(variant=self.variant, lot_code="COUNT", quantity=10, unit_cost=0, actor=self.admin, reference="RECEPTION-COUNT")
        count = InventoryService.start_count(actor=self.admin, reference="INV-TEST")
        line = count.lines.get(variant=self.variant)
        InventoryService.set_count_line(line=line, counted_quantity=7)
        InventoryService.complete_count(count=count, actor=self.admin)
        self.assertEqual(StockLot.objects.filter(variant=self.variant).values_list("quantity_available", flat=True).first(), 7)
        self.assertTrue(StockMovement.objects.filter(reference="INV-TEST", movement_type=StockMovement.Type.ADJUSTMENT, quantity_delta=-3).exists())
        self.assertEqual(InventoryCount.objects.get(pk=count.pk).status, InventoryCount.Status.COMPLETED)
