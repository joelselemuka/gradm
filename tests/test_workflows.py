from datetime import date, timedelta
from decimal import Decimal
import re
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from apps.accounts.models import User
from apps.inventory.models import StockLot, StockMovement
from apps.inventory.services import InventoryService
from apps.products.forms import NewArticleForm
from apps.products.models import Brand, Category, Product, ProductVariant
from apps.pos.models import CashRegister, CashSession, CashTransaction
from apps.pos.selectors import cash_report_for
from apps.pos.services import CashSessionService
from apps.sales.models import Invoice, Payment
from apps.sales.services import InvoiceService, SaleItem, SaleService
from apps.suppliers.models import Supplier
from apps.purchases.models import PurchaseOrder, PurchaseOrderLine
from apps.purchases.services import PurchaseService
from apps.purchases.models import ReplenishmentNeed
from apps.expenses.models import Expense
from apps.expenses.services import ExpenseService
from apps.core.models import StoreSettings
from apps.core.forms import StoreSettingsForm
from apps.reports.services import send_general_report


class CriticalWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="test", role=User.Role.ADMIN)
        self.cashier = User.objects.create_user("cashier", password="test", role=User.Role.CASHIER)
        self.manager = User.objects.create_user("manager", password="test", role=User.Role.MANAGER)
        product = Product.objects.create(name="Lotion", internal_reference="LOT-001", expiration_managed=True, expiration_date=date.today() + timedelta(days=30))
        self.variant = ProductVariant.objects.create(product=product, name="350 ml", sku="LOT-350", barcode="10000001", purchase_price=Decimal("3000"), sale_price=Decimal("5000"))
        self.register = CashRegister.objects.create(name="Caisse 1")
        self.cash_session = CashSessionService.open_session(register=self.register, actor=self.cashier)

    def test_sale_uses_fefo_and_never_consumes_expired_lot(self):
        expired = InventoryService.receive(variant=self.variant, lot_code="OLD", quantity=5, unit_cost=Decimal("3000"), expires_at=date.today() - timedelta(days=1), actor=self.admin, reference="REC-1")
        fresh = InventoryService.receive(variant=self.variant, lot_code="NEW", quantity=5, unit_cost=Decimal("3000"), expires_at=date.today() + timedelta(days=3), actor=self.admin, reference="REC-2")
        invoice = SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 2)], payment_method=Payment.Method.CASH, cash_received=Decimal("10000"))
        expired.refresh_from_db(); fresh.refresh_from_db()
        self.assertEqual(expired.quantity_available, 5)
        self.assertEqual(fresh.quantity_available, 3)
        self.assertEqual(invoice.total, Decimal("10000.00"))

    def test_insufficient_stock_rolls_back_invoice_and_stock(self):
        lot = InventoryService.receive(variant=self.variant, lot_code="A", quantity=1, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-1")
        with self.assertRaises(ValidationError):
            SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 2)], payment_method=Payment.Method.CASH, cash_received=Decimal("10000"))
        lot.refresh_from_db()
        self.assertEqual(lot.quantity_available, 1)
        self.assertFalse(Invoice.objects.exists())

    def test_only_admin_can_cancel_invoice_and_cancellation_restores_stock(self):
        lot = InventoryService.receive(variant=self.variant, lot_code="A", quantity=2, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-1")
        invoice = SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 2)], payment_method=Payment.Method.CARD)
        with self.assertRaises(PermissionDenied):
            InvoiceService.cancel_invoice(invoice=invoice, actor=self.manager, reason="Erreur")
        InvoiceService.cancel_invoice(invoice=invoice, actor=self.admin, reason="Erreur de saisie")
        lot.refresh_from_db(); invoice.refresh_from_db()
        self.assertEqual(lot.quantity_available, 2)
        self.assertEqual(invoice.status, Invoice.Status.CANCELLED)
        self.assertEqual(StockMovement.objects.filter(movement_type=StockMovement.Type.SALE_CANCELLED).count(), 1)

    def test_admin_cannot_cancel_a_past_invoice(self):
        InventoryService.receive(variant=self.variant, lot_code="PAST", quantity=1, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-PAST")
        invoice = SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 1)], payment_method=Payment.Method.CARD)
        Invoice.objects.filter(pk=invoice.pk).update(created_at=timezone.now() - timedelta(days=1))
        invoice.refresh_from_db()
        with self.assertRaises(ValidationError):
            InvoiceService.cancel_invoice(invoice=invoice, actor=self.admin, reason="Trop tard")

    def test_admin_gets_read_only_pos_overview(self):
        self.client.force_login(self.admin)
        response = self.client.get("/sales/pos/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vue de contrôle uniquement")

    def test_dashboards_filter_sales_by_custom_range_and_period(self):
        InventoryService.receive(variant=self.variant, lot_code="FILTER", quantity=2, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-FILTER")
        invoice = SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 1)], payment_method=Payment.Method.CASH, cash_received=Decimal("5000"))
        current = timezone.localdate()
        self.client.force_login(self.admin)
        params = {"period": "custom", "date_from": current.isoformat(), "date_to": current.isoformat()}
        dashboard = self.client.get("/", params)
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.context["period_sales"], 1)
        self.assertEqual(dashboard.context["period_revenue"], invoice.total)
        self.assertContains(dashboard, invoice.number)
        pos = self.client.get("/sales/pos/", {"period": "year", "date": current.isoformat()})
        self.assertEqual(pos.status_code, 200)
        self.assertEqual(pos.context["invoice_count"], 1)
        outside = self.client.get("/", {"period": "custom", "date_from": (current - timedelta(days=2)).isoformat(), "date_to": (current - timedelta(days=1)).isoformat()})
        self.assertEqual(outside.context["period_sales"], 0)

    def test_new_session_does_not_show_sales_from_previous_session(self):
        InventoryService.receive(variant=self.variant, lot_code="SESSION-OLD", quantity=1, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-SESSION")
        old_invoice = SaleService.create_sale(
            actor=self.cashier,
            items=[SaleItem(self.variant.pk, 1)],
            payment_method=Payment.Method.CASH,
            cash_received=Decimal("5000"),
        )
        CashSessionService.close_session(
            session=self.cash_session,
            actor=self.cashier,
            sales_deposit_local_amount=old_invoice.total,
            sales_deposit_foreign_amount=Decimal("0"),
            counted_local_amount=Decimal("0"),
            counted_foreign_amount=Decimal("0"),
        )
        new_session = CashSessionService.open_session(
            register=self.register,
            actor=self.admin,
            cashier=self.cashier,
        )
        self.client.force_login(self.cashier)
        dashboard = self.client.get("/", {"period": "day"})
        self.assertEqual(dashboard.context["period_sales"], 0)
        self.assertNotContains(dashboard, old_invoice.number)
        invoices = self.client.get("/sales/invoices/")
        self.assertNotContains(invoices, old_invoice.number)
        self.assertEqual(self.client.get(f"/sales/invoices/{old_invoice.pk}/").status_code, 403)

    def test_pos_requires_open_session_owned_by_authenticated_cashier(self):
        self.client.force_login(self.cashier)
        pos_response = self.client.get("/sales/pos/")
        self.assertEqual(pos_response.status_code, 200)
        self.assertContains(pos_response, "Clôturer la vente")
        self.assertContains(pos_response, f"/cash/sessions/{self.cash_session.pk}/close/")
        self.client.force_login(self.manager)
        response = self.client.get("/sales/pos/")
        self.assertRedirects(response, "/users/login/?next=/sales/pos/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.client.force_login(self.manager)
        response = self.client.post("/sales/pos/cart/add/", {"variant_id": self.variant.pk})
        self.assertRedirects(response, f"/users/login/?next=/sales/pos/cart/add/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_pos_middleware_blocks_cashier_without_open_session_on_every_pos_endpoint(self):
        self.cash_session.status = CashSession.Status.CLOSED
        self.cash_session.save(update_fields=["status"])
        self.client.force_login(self.cashier)

        response = self.client.get("/sales/pos/")
        self.assertRedirects(response, "/users/login/?next=/sales/pos/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.client.force_login(self.cashier)
        response = self.client.post("/sales/pos/cart/add/", {"variant_id": self.variant.pk})
        self.assertRedirects(response, "/users/login/?next=/sales/pos/cart/add/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_shows_open_session_error_and_does_not_authenticate_cashier(self):
        self.cash_session.status = CashSession.Status.CLOSED
        self.cash_session.save(update_fields=["status"])

        response = self.client.post(
            "/users/login/",
            {"username": "cashier", "password": "test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aucune session ouverte pour cet utilisateur")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_closing_session_logs_cashier_out_and_hides_closed_session(self):
        self.client.force_login(self.cashier)
        response = self.client.post(
            f"/cash/sessions/{self.cash_session.pk}/close/",
            {"counted_local_amount": "0", "counted_foreign_amount": "0"},
        )
        self.assertRedirects(response, "/users/login/")
        self.cash_session.refresh_from_db()
        self.assertEqual(self.cash_session.status, CashSession.Status.CLOSED)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.client.force_login(self.cashier)
        response = self.client.get("/sales/pos/")
        self.assertRedirects(response, "/users/login/?next=/sales/pos/")
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(f"/cash/sessions/{self.cash_session.pk}/").status_code, 403)
        self.assertEqual(self.client.get("/cash/").status_code, 200)
        self.assertContains(self.client.get("/cash/"), "Aucune session de cash ouverte")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/cash/sessions/{self.cash_session.pk}/close/").status_code, 200)

    def test_closure_compares_sales_deposit_in_fc_and_usd_at_daily_rate(self):
        settings = StoreSettings.get_solo()
        settings.exchange_rate = Decimal("2300")
        settings.save()
        self.variant.sale_price = Decimal("780000")
        self.variant.save(update_fields=["sale_price"])
        InventoryService.receive(variant=self.variant, lot_code="DEPOSIT", quantity=1, unit_cost=Decimal("300000"), actor=self.admin, reference="REC-DEPOSIT")
        SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 1)], payment_method=Payment.Method.CARD)
        CashSessionService.close_session(
            session=self.cash_session,
            actor=self.cashier,
            sales_deposit_local_amount=Decimal("435000"),
            sales_deposit_foreign_amount=Decimal("150"),
            counted_local_amount=Decimal("0"),
            counted_foreign_amount=Decimal("0"),
        )
        self.cash_session.refresh_from_db()
        self.assertEqual(self.cash_session.expected_sales, Decimal("780000.00"))
        self.assertEqual(self.cash_session.sales_difference, Decimal("0.00"))
        self.assertEqual(self.cash_session.difference, Decimal("0.00"))

    def test_pos_catalog_is_populated_and_htmx_search_matches_reference(self):
        self.client.force_login(self.cashier)
        initial = self.client.get("/sales/pos/")
        self.assertEqual(initial.status_code, 200)
        self.assertContains(initial, "Lotion")
        self.client.post("/sales/pos/cart/add/", {"variant_id": self.variant.pk})
        with_cart = self.client.get("/sales/pos/")
        self.assertContains(with_cart, 'data-subtotal="5000.00"')
        self.assertContains(with_cart, "<strong>5.000</strong>")
        self.assertContains(with_cart, 'hx-trigger="input changed delay:350ms"')
        searched = self.client.get("/sales/pos/", {"q": "LOT-001"}, HTTP_HX_REQUEST="true")
        self.assertEqual(searched.status_code, 200)
        self.assertContains(searched, "Lotion")
        self.assertNotContains(searched, "pos-workspace")

    def test_exact_barcode_scan_adds_and_repeated_scan_increments_cart(self):
        self.client.force_login(self.cashier)
        search = self.client.get("/sales/pos/", {"q": self.variant.barcode}, HTTP_HX_REQUEST="true")
        self.assertContains(search, "hx-post=\"/sales/pos/cart/add/\"")
        payload = {"variant_id": self.variant.pk, "q": self.variant.barcode}
        first = self.client.post("/sales/pos/cart/add/", payload, HTTP_HX_REQUEST="true")
        second = self.client.post("/sales/pos/cart/add/", payload, HTTP_HX_REQUEST="true")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertContains(first, 'data-subtotal="5000.00"')
        self.assertContains(second, "pos-cart-lines")
        self.assertEqual(self.client.session["pos_cart"][str(self.variant.pk)], 2)
        updated = self.client.post(f"/sales/pos/cart/{self.variant.pk}/", {"quantity": "3"}, HTTP_HX_REQUEST="true")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.session["pos_cart"][str(self.variant.pk)], 3)
        self.assertContains(updated, 'data-subtotal="15000.00"')
        removed = self.client.post(f"/sales/pos/cart/{self.variant.pk}/", {"remove": "1"}, HTTP_HX_REQUEST="true")
        self.assertEqual(removed.status_code, 200)
        self.assertNotIn(str(self.variant.pk), self.client.session.get("pos_cart", {}))

    def test_pos_preview_is_not_persisted_and_final_validation_prints(self):
        store_settings = StoreSettings.get_solo()
        store_settings.discounts_enabled = True
        store_settings.manual_discount_limit = Decimal("1000")
        store_settings.save()
        InventoryService.receive(variant=self.variant, lot_code="POS", quantity=4, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-POS")
        self.client.force_login(self.cashier)
        self.client.post("/sales/pos/cart/add/", {"variant_id": self.variant.pk})
        draft_number = self.client.session["pos_invoice_number"]
        preview = self.client.post("/sales/pos/preview/", {"cash_received": "5000", "manual_discount": "500", "customer_name": "Client comptoir", "customer_phone": "0990000000"})
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Aperçu de la facture")
        self.assertContains(preview, "4.500")
        self.assertEqual(Invoice.objects.count(), 0)
        response = self.client.post("/sales/pos/checkout/", {"cash_received": "5000", "manual_discount": "500", "customer_name": "Client comptoir", "customer_phone": "0990000000"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("print=1", response["Location"])
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.number, draft_number)
        self.assertEqual(invoice.subtotal, Decimal("5000.00"))
        self.assertEqual(invoice.manual_discount, Decimal("500.00"))
        self.assertEqual(invoice.total, Decimal("4500.00"))
        self.assertEqual(invoice.payments.get().amount, Decimal("4500.00"))
        self.assertEqual(invoice.customer_phone, "0990000000")
        self.assertRegex(invoice.number, rf"^FAC-{timezone.localdate():%Y%m%d}-[A-F0-9]{{6}}$")
        self.assertEqual(self.client.session.get("pos_cart", {}), {})
        self.assertNotIn("pos_invoice_number", self.client.session)
        self.assertEqual(StockLot.objects.get(variant=self.variant, code="POS").quantity_available, 3)
        ticket = self.client.get(f"/sales/invoices/{invoice.pk}/?print=1")
        self.assertEqual(ticket.status_code, 200)
        self.assertContains(ticket, "Merci pour votre achat")
        self.assertContains(ticket, "NET À PAYER")
        self.assertNotContains(ticket, "app-shell")
        dashboard = self.client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Produits les plus vendus")
        self.assertContains(dashboard, "Lotion")
        self.client.post("/sales/pos/cart/add/", {"variant_id": self.variant.pk})
        self.assertNotEqual(self.client.session["pos_invoice_number"], draft_number)

    def test_configured_threshold_promotion_and_manual_limit_are_server_enforced(self):
        settings = StoreSettings.get_solo()
        settings.discounts_enabled = True
        settings.promotion_enabled = True
        settings.promotion_threshold = Decimal("4000")
        settings.promotion_type = StoreSettings.DiscountType.PERCENT
        settings.promotion_value = Decimal("10")
        settings.manual_discount_limit = Decimal("500")
        settings.save()
        quote = SaleService.quote_sale(items=[SaleItem(self.variant.pk, 1)])
        self.assertEqual(quote["promotion_discount"], Decimal("500.00"))
        self.assertEqual(quote["total"], Decimal("4500.00"))
        settings.promotion_type = StoreSettings.DiscountType.FIXED
        settings.promotion_value = Decimal("1000")
        settings.save()
        fixed_quote = SaleService.quote_sale(items=[SaleItem(self.variant.pk, 1)])
        self.assertEqual(fixed_quote["promotion_discount"], Decimal("1000.00"))
        self.assertEqual(fixed_quote["total"], Decimal("4000.00"))
        with self.assertRaises(ValidationError):
            SaleService.quote_sale(items=[SaleItem(self.variant.pk, 1)], manual_discount=Decimal("501"))

    def test_settings_page_is_admin_only(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/settings/").status_code, 200)
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get("/settings/").status_code, 403)

    def test_discount_configuration_fields_are_optional_when_disabled(self):
        settings = StoreSettings.get_solo()
        settings.promotion_threshold = Decimal("200000")
        settings.promotion_value = Decimal("5")
        settings.manual_discount_limit = Decimal("10000")
        settings.save()
        payload = {"name": "GSM", "currency": "FC", "invoice_prefix": "FAC", "low_stock_threshold": "5", "expiry_alert_days": "30", "exchange_rate": "1.00"}
        disabled_form = StoreSettingsForm(payload, instance=settings)
        self.assertTrue(disabled_form.is_valid(), disabled_form.errors)
        saved = disabled_form.save()
        self.assertEqual(saved.promotion_threshold, Decimal("200000.00"))
        enabled_form = StoreSettingsForm({**payload, "discounts_enabled": "on"}, instance=settings)
        self.assertFalse(enabled_form.is_valid())
        self.assertIn("promotion_threshold", enabled_form.errors)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_general_report_uses_recipient_configured_in_settings(self):
        settings = StoreSettings.get_solo()
        settings.report_recipient_email = "direction@example.com"
        settings.save()
        self.assertTrue(send_general_report())
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["direction@example.com"])
        self.assertIn("VENTE DU JOUR", message.body)
        self.assertIn("CASH DU JOUR", message.body)

    def test_general_report_keeps_sales_expenses_out_of_cash_movements(self):
        from apps.reports.services import build_report_data

        CashSessionService.record_movement(
            session=self.cash_session,
            actor=self.admin,
            direction=CashTransaction.Direction.IN,
            category=CashTransaction.Category.OWNER_DEPOSIT,
            amount=Decimal("3000"),
            description="Fonds cash",
        )
        InventoryService.receive(variant=self.variant, lot_code="REPORT", quantity=2, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-REPORT")
        SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 2)], payment_method=Payment.Method.CASH, cash_received=Decimal("10000"))
        CashSessionService.record_movement(
            session=self.cash_session,
            actor=self.admin,
            direction=CashTransaction.Direction.OUT,
            category=CashTransaction.Category.PURCHASE,
            amount=Decimal("2000"),
            description="Achat cash",
        )
        expense = Expense.objects.create(
            category="Transport",
            amount=Decimal("100"),
            description="Dépense vente",
            expense_date=date.today(),
            requester=self.manager,
            paid_in_cash=True,
            cash_session=self.cash_session,
        )
        ExpenseService.approve(expense=expense, actor=self.admin)
        report = build_report_data(date.today())
        self.assertEqual(report["total_sales"], Decimal("10000.00"))
        self.assertEqual(report["sales_balance"], Decimal("9900.00"))
        self.assertEqual(report["cash_balance_local"], Decimal("1000.00"))
        self.assertEqual(report["outings_local"], Decimal("2000.00"))

    def test_exchange_uses_configured_store_rate(self):
        settings = StoreSettings.get_solo()
        settings.exchange_rate = Decimal("750")
        settings.save()
        outgoing, incoming = CashSessionService.record_exchange(session=self.cash_session, actor=self.admin, cash_out=Decimal("500"), cash_in=Decimal("600"), foreign_currency="USD", foreign_amount=Decimal("1"), description="Change client")
        self.assertEqual(outgoing.exchange_rate, Decimal("750.00"))
        self.assertEqual(incoming.exchange_rate, Decimal("750.00"))
        self.assertEqual(str(outgoing.exchange_rate), "750.00")

    def test_cannot_open_multiple_sessions_for_cashier_or_register(self):
        with self.assertRaises(ValidationError):
            CashSessionService.open_session(register=self.register, actor=self.manager)
        other_register = CashRegister.objects.create(name="Caisse 2")
        with self.assertRaises(ValidationError):
            CashSessionService.open_session(register=other_register, actor=self.cashier)

    def test_low_stock_creates_one_replenishment_need(self):
        InventoryService.receive(variant=self.variant, lot_code="ALERT", quantity=5, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-ALERT")
        self.assertEqual(ReplenishmentNeed.objects.filter(variant=self.variant, status=ReplenishmentNeed.Status.OPEN).count(), 1)

    def test_admin_supervision_pages_render(self):
        self.client.force_login(self.admin)
        for path in ("/sales/invoices/", "/products/", "/inventory/", "/purchases/", "/reports/", "/audit/", "/cash/", "/expenses/"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_admin_filtered_management_pages_and_pagination_render(self):
        self.client.force_login(self.admin)
        paths = (
            "/cash/sessions/?status=OPEN",
            "/cash/?date=2026-08-19&cashier=1",
            "/reports/?period=month&type=cash",
            "/expenses/?date=2026-08-19&session=1&user=1",
            "/customers/",
            "/suppliers/",
            "/promotions/",
            "/products/categories/",
        )
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_general_report_detail_uses_written_report_format(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/reports/{date.today():%Y-%m-%d}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rapport général de vente et du cash")
        self.assertContains(response, "Vente du jour")
        self.assertContains(response, "Cash du jour")
        self.assertContains(response, "Solde général")
        self.assertContains(response, "Solde versement")

    def test_expiry_and_low_stock_alerts_are_deduplicated_and_link_to_exact_lists(self):
        from apps.inventory.tasks import scan_expiration_alerts
        from apps.notifications.models import Notification

        InventoryService.receive(variant=self.variant, lot_code="EXPIRED-A", quantity=3, unit_cost=Decimal("3000"), actor=self.admin, expires_at=date.today() - timedelta(days=1), reference="EXP-A")
        InventoryService.receive(variant=self.variant, lot_code="EXPIRED-B", quantity=2, unit_cost=Decimal("3000"), actor=self.admin, expires_at=date.today() - timedelta(days=1), reference="EXP-B")
        scan_expiration_alerts()
        expired_notice = Notification.objects.filter(recipient=self.admin, title="Produits expirés").latest("created_at")
        self.assertIn("1 produit", expired_notice.message)
        self.assertEqual(expired_notice.target_url, "/inventory/alerts/expired/")
        self.client.force_login(self.admin)
        expired_page = self.client.get(expired_notice.target_url)
        self.assertEqual(expired_page.status_code, 200)
        self.assertContains(expired_page, (date.today() - timedelta(days=1)).strftime("%d/%m/%Y"))
        self.assertContains(expired_page, "Lotion")

        low_notice = Notification.objects.filter(recipient=self.admin, title="Stock faible").latest("created_at")
        self.assertIn("1 produit", low_notice.message)
        self.assertEqual(self.client.get(low_notice.target_url).status_code, 200)

    def test_cashier_expense_page_renders_without_date_or_session_fields(self):
        self.client.force_login(self.cashier)
        response = self.client.get("/expenses/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="expense_date"')
        self.assertNotContains(response, 'name="cash_session"')

    def test_cashier_expense_list_only_shows_the_open_session(self):
        old_register = CashRegister.objects.create(name="Ancienne caisse")
        old_session = CashSession.objects.create(
            register=old_register,
            cashier=self.cashier,
            status=CashSession.Status.CLOSED,
            opening_amount=Decimal("0"),
        )
        Expense.objects.create(
            category="Ancienne dépense",
            amount=Decimal("50"),
            description="Dépense de la session clôturée",
            expense_date=date.today() - timedelta(days=1),
            requester=self.cashier,
            cash_session=old_session,
        )
        Expense.objects.create(
            category="Dépense actuelle",
            amount=Decimal("25"),
            description="Dépense de la session ouverte",
            expense_date=date.today(),
            requester=self.cashier,
            cash_session=self.cash_session,
        )
        self.client.force_login(self.cashier)
        response = self.client.get("/expenses/")
        self.assertContains(response, "Dépense actuelle")
        self.assertNotContains(response, "Ancienne dépense")

    def test_perishable_article_requires_expiration_date_server_side(self):
        category = Category.objects.create(name="Alimentation")
        payload = {"name": "Yaourt", "internal_reference": "YAO-001", "category": category.pk, "sku": "YAO-NAT", "sale_price": "100", "low_stock_threshold": "3", "expiration_managed": "on"}
        form = NewArticleForm(payload)
        self.assertFalse(form.is_valid())
        payload["expiration_date"] = "2026-12-31"
        form = NewArticleForm(payload)
        self.assertTrue(form.is_valid(), form.errors)
        variant = form.save()
        self.assertEqual(variant.purchase_price, Decimal("0.00"))
        self.assertEqual(variant.product.expiration_date, date(2026, 12, 31))

    def test_admin_can_quick_create_category_with_htmx(self):
        self.client.force_login(self.admin)
        response = self.client.post("/products/categories/quick-create/", {"name": "Hygiène"}, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Category.objects.filter(name="Hygiène").exists())
        self.assertContains(response, "hx-swap-oob")
        self.assertEqual(self.client.get("/products/new/").status_code, 200)

    def test_admin_can_edit_category_and_free_text_brand_creates_brand(self):
        category = Category.objects.create(name="Boissons")
        self.client.force_login(self.admin)
        response = self.client.post(f"/products/categories/{category.pk}/update/", {"name": "Boissons fraîches", "parent": "", "active": "on"})
        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name, "Boissons fraîches")
        form = NewArticleForm({"name": "Eau", "internal_reference": "EAU-001", "category": category.pk, "brand": "Source locale", "sku": "EAU-1L", "sale_price": "50", "low_stock_threshold": "2"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertTrue(Brand.objects.filter(name="Source locale").exists())

    def test_article_create_redirects_to_list_and_catalogue_actions_work(self):
        category = Category.objects.create(name="Entretien")
        self.client.force_login(self.admin)
        response = self.client.post("/products/new/", {"name": "Savon", "internal_reference": "SAV-001", "category": category.pk, "brand": "Maison", "sku": "SAV-STD", "sale_price": "125", "low_stock_threshold": "4"})
        self.assertRedirects(response, "/products/")
        product = Product.objects.get(internal_reference="SAV-001")
        self.assertContains(self.client.get("/products/"), "125,00")
        self.assertEqual(self.client.post(f"/products/{product.pk}/toggle/").status_code, 302)
        product.refresh_from_db()
        self.assertFalse(product.active)
        self.assertEqual(self.client.post(f"/products/{product.pk}/delete/").status_code, 302)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_product_detail_contains_stock_and_recent_sales_sections(self):
        InventoryService.receive(variant=self.variant, lot_code="DETAIL", quantity=1, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-DETAIL")
        SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 1)], payment_method=Payment.Method.CARD)
        self.client.force_login(self.admin)
        response = self.client.get(f"/products/{self.variant.product_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrées et sorties récentes")
        self.assertContains(response, "5 dernières ventes")

    def test_cash_ledger_integrates_sales_expenses_exchange_and_carryover(self):
        CashSessionService.record_movement(session=self.cash_session, actor=self.admin, direction=CashTransaction.Direction.IN, category=CashTransaction.Category.OWNER_DEPOSIT, amount=Decimal("3000"), description="Fonds donne par le boss")
        InventoryService.receive(variant=self.variant, lot_code="A", quantity=2, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-1")
        invoice = SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 2)], payment_method=Payment.Method.CASH, cash_received=Decimal("10000"))
        self.assertEqual(invoice.cash_session, self.cash_session)
        CashSessionService.record_movement(session=self.cash_session, actor=self.admin, direction=CashTransaction.Direction.OUT, category=CashTransaction.Category.PURCHASE, amount=Decimal("2000"), description="Achat urgent")
        CashSessionService.record_exchange(session=self.cash_session, actor=self.admin, cash_out=Decimal("500"), cash_in=Decimal("600"), foreign_currency="USD", foreign_amount=Decimal("1"), description="Change client")
        report = cash_report_for(self.cash_session)
        self.assertEqual(report.cash_sales, Decimal("10000"))
        self.assertEqual(report.expected_cash, Decimal("1100"))
        CashSessionService.close_session(session=self.cash_session, actor=self.cashier, counted_cash=Decimal("1100"))
        self.cash_session.refresh_from_db()
        self.assertEqual(self.cash_session.difference, Decimal("0"))
        self.assertEqual(cash_report_for(self.cash_session).carryover_cash, Decimal("1100"))

    def test_cash_session_tracks_fc_usd_movements_exchange_and_closure(self):
        settings = StoreSettings.get_solo()
        settings.exchange_rate = Decimal("2500")
        settings.save()
        register = CashRegister.objects.create(name="Caisse USD")
        session = CashSessionService.open_session(register=register, actor=self.admin, cashier=self.manager, opening_local_amount=Decimal("2500000"), opening_foreign_amount=Decimal("550"))
        CashSessionService.record_movement(session=session, actor=self.manager, direction=CashTransaction.Direction.OUT, category=CashTransaction.Category.PURCHASE, local_amount=Decimal("850000"), foreign_amount=Decimal("300"), description="Achat fournisseur")
        CashSessionService.record_movement(session=session, actor=self.manager, direction=CashTransaction.Direction.IN, category=CashTransaction.Category.OWNER_DEPOSIT, local_amount=Decimal("100000"), foreign_amount=Decimal("50"), description="Apport complémentaire")
        CashSessionService.record_currency_exchange(session=session, actor=self.manager, local_out=Decimal("250000"), foreign_in=Decimal("100"), description="Change client")
        report = cash_report_for(session)
        self.assertEqual(report.expected_local, Decimal("1500000.00"))
        self.assertEqual(report.expected_foreign, Decimal("400.00"))
        self.assertEqual(report.expected_cash, Decimal("2500000.00"))
        CashSessionService.close_session(session=session, actor=self.manager, counted_local_amount=Decimal("1500000"), counted_foreign_amount=Decimal("400"))
        session.refresh_from_db()
        self.assertEqual(session.difference, Decimal("0.00"))
        self.assertEqual(session.counted_foreign_amount, Decimal("400.00"))

    def test_cash_permissions_and_closed_session_are_enforced(self):
        with self.assertRaises(PermissionDenied):
            CashSessionService.record_movement(session=self.cash_session, actor=self.cashier, direction=CashTransaction.Direction.OUT, category=CashTransaction.Category.EXPENSE, amount=Decimal("20"), description="Tentative")
        CashSessionService.close_session(session=self.cash_session, actor=self.cashier, counted_cash=Decimal("0"))
        with self.assertRaises(ValidationError):
            CashSessionService.record_movement(session=self.cash_session, actor=self.admin, direction=CashTransaction.Direction.OUT, category=CashTransaction.Category.EXPENSE, amount=Decimal("20"), description="Tardif")

    def test_voiding_an_exchange_keeps_history_and_removes_its_cash_effect(self):
        outgoing, incoming = CashSessionService.record_exchange(session=self.cash_session, actor=self.admin, cash_out=Decimal("500"), cash_in=Decimal("600"), foreign_currency="USD", foreign_amount=Decimal("1"), description="Change client")
        self.assertEqual(cash_report_for(self.cash_session).expected_cash, Decimal("100"))
        CashSessionService.void_movement(movement=outgoing, actor=self.admin, reason="Erreur de saisie")
        outgoing.refresh_from_db(); incoming.refresh_from_db()
        self.assertTrue(outgoing.is_voided)
        self.assertTrue(incoming.is_voided)
        self.assertEqual(cash_report_for(self.cash_session).expected_cash, Decimal("0"))

    def test_owner_can_open_and_fund_a_cashier_session_and_access_report(self):
        register = CashRegister.objects.create(name="Caisse 2")
        session = CashSessionService.open_session(register=register, actor=self.admin, cashier=self.manager, opening_amount=Decimal("2500"))
        self.assertEqual(session.cashier, self.manager)
        self.assertEqual(session.cash_transactions.get().category, CashTransaction.Category.OPENING_FLOAT)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/cash/").status_code, 200)
        report_page = self.client.get(f"/cash/sessions/{session.pk}/")
        self.assertRedirects(report_page, f"/cash/?session={session.pk}")
        cash_page = self.client.get("/cash/")
        self.assertContains(cash_page, "Entrée cash")
        self.assertContains(cash_page, "Sortie cash")
        close_page = self.client.get(f"/cash/sessions/{session.pk}/close/")
        self.assertEqual(close_page.status_code, 200)
        self.assertContains(close_page, "Clôturer la vente")

    def test_cash_purchase_receipt_updates_stock_and_cash_ledger(self):
        supplier = Supplier.objects.create(name="Fournisseur A")
        order = PurchaseOrder.objects.create(supplier=supplier, reference="PO-001", paid_in_cash=True, cash_session=self.cash_session, created_by=self.admin)
        line = PurchaseOrderLine.objects.create(order=order, variant=self.variant, ordered_quantity=3, unit_cost=Decimal("3000"))
        CashSessionService.record_movement(session=self.cash_session, actor=self.admin, direction=CashTransaction.Direction.IN, category=CashTransaction.Category.OWNER_DEPOSIT, amount=Decimal("9000"), description="Fonds achat")
        PurchaseService.receive_line(order=order, line=line, quantity=3, lot_code="PUR-1", expires_at=None, actor=self.admin)
        line.refresh_from_db()
        self.assertEqual(line.received_quantity, 3)
        self.assertEqual(order.cash_session.cash_transactions.filter(category=CashTransaction.Category.PURCHASE).get().amount, Decimal("9000"))

    def test_bulk_stock_operations_group_multiple_articles_without_unit_cost_ui(self):
        other_product = Product.objects.create(name="Savon", internal_reference="SAV-BULK")
        other_variant = ProductVariant.objects.create(product=other_product, name="Article", sku="SAV-BULK", sale_price=Decimal("150"), purchase_price=Decimal("0"))
        InventoryService.receive_batch(lines=[{"variant": self.variant, "quantity": 3, "lot_code": "BULK-A"}, {"variant": other_variant, "quantity": 4, "lot_code": "BULK-B"}], actor=self.admin, reference="REC-BULK")
        self.assertEqual(StockLot.objects.get(variant=self.variant, code="BULK-A").quantity_available, 3)
        self.assertEqual(StockLot.objects.get(variant=other_variant, code="BULK-B").quantity_available, 4)
        InventoryService.issue_batch(lines=[{"variant": self.variant, "quantity": 1}, {"variant": other_variant, "quantity": 2}], actor=self.admin, reference="SORT-BULK", reason="Casse")
        self.assertEqual(StockLot.objects.get(variant=self.variant, code="BULK-A").quantity_available, 2)
        self.assertEqual(StockLot.objects.get(variant=other_variant, code="BULK-B").quantity_available, 2)
        self.client.force_login(self.admin)
        response = self.client.get("/inventory/operations/?mode=receive")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Coût unitaire")

    def test_approved_cash_expense_creates_cash_outflow_once(self):
        InventoryService.receive(variant=self.variant, lot_code="EXPENSE-SALE", quantity=1, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-EXPENSE")
        SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 1)], payment_method=Payment.Method.CASH, cash_received=Decimal("5000"))
        expense = Expense.objects.create(category="Transport", amount=Decimal("250"), description="Livraison", expense_date=date.today(), requester=self.manager, paid_in_cash=True, cash_session=self.cash_session)
        ExpenseService.approve(expense=expense, actor=self.admin)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.APPROVED)
        self.assertEqual(self.cash_session.cash_transactions.filter(category=CashTransaction.Category.EXPENSE).get().amount, Decimal("250"))
        with self.assertRaises(ValidationError): ExpenseService.approve(expense=expense, actor=self.admin)

    def test_cash_out_and_expense_cannot_exceed_available_balance(self):
        with self.assertRaisesMessage(ValidationError, "supérieure au solde disponible"):
            CashSessionService.record_movement(
                session=self.cash_session,
                actor=self.admin,
                direction=CashTransaction.Direction.OUT,
                category=CashTransaction.Category.WITHDRAWAL,
                local_amount=Decimal("1"),
                description="Retrait trop élevé",
            )

        CashSessionService.record_movement(
            session=self.cash_session,
            actor=self.admin,
            direction=CashTransaction.Direction.IN,
            category=CashTransaction.Category.OWNER_DEPOSIT,
            local_amount=Decimal("100"),
            foreign_amount=Decimal("2"),
            description="Fonds disponibles",
        )
        with self.assertRaisesMessage(ValidationError, "supérieure au solde disponible"):
            CashSessionService.record_movement(
                session=self.cash_session,
                actor=self.admin,
                direction=CashTransaction.Direction.OUT,
                category=CashTransaction.Category.WITHDRAWAL,
                local_amount=Decimal("101"),
                description="Retrait supérieur au solde",
            )
        with self.assertRaisesMessage(ValidationError, "supérieure au solde disponible"):
            CashSessionService.record_movement(
                session=self.cash_session,
                actor=self.admin,
                direction=CashTransaction.Direction.OUT,
                category=CashTransaction.Category.WITHDRAWAL,
                foreign_amount=Decimal("3"),
                description="Retrait USD supérieur au solde",
            )

        expense = Expense.objects.create(
            category="Transport",
            amount=Decimal("101"),
            description="Dépense supérieure au solde",
            expense_date=date.today(),
            requester=self.manager,
            paid_in_cash=True,
            cash_session=self.cash_session,
        )
        with self.assertRaises(ValidationError):
            ExpenseService.approve(expense=expense, actor=self.admin)
        expense.refresh_from_db()
        self.assertEqual(expense.status, Expense.Status.PENDING)
        self.assertFalse(self.cash_session.cash_transactions.filter(category=CashTransaction.Category.EXPENSE).exists())

    def test_expense_submission_uses_today_and_open_session_and_notifies_admin(self):
        from apps.notifications.models import Notification
        InventoryService.receive(variant=self.variant, lot_code="SUBMIT-SALE", quantity=1, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-SUBMIT")
        SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 1)], payment_method=Payment.Method.CASH, cash_received=Decimal("5000"))
        expense = ExpenseService.submit(actor=self.cashier, category="Transport", amount=Decimal("125"), description="Livraison urgente")
        self.assertEqual(expense.expense_date, timezone.localdate())
        self.assertEqual(expense.cash_session_id, self.cash_session.pk)
        notice = Notification.objects.get(recipient=self.admin, title="Dépense à approuver")
        self.assertEqual(notice.target_url, f"/expenses/{expense.pk}/")
        self.client.force_login(self.admin)
        response = self.client.get(notice.target_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approuver et enregistrer la sortie cash")

    def test_expense_submission_rejects_amount_above_current_cash(self):
        self.variant.sale_price = Decimal("365750")
        self.variant.save(update_fields=["sale_price"])
        InventoryService.receive(variant=self.variant, lot_code="SALES-365750", quantity=1, unit_cost=Decimal("3000"), actor=self.admin, reference="REC-SALES")
        SaleService.create_sale(actor=self.cashier, items=[SaleItem(self.variant.pk, 1)], payment_method=Payment.Method.CASH, cash_received=Decimal("365750"))
        with self.assertRaisesMessage(ValidationError, "Demande refusée"):
            ExpenseService.submit(
                actor=self.cashier,
                category="Transport",
                amount=Decimal("400000"),
                description="Dépense supérieure aux ventes",
            )
        self.assertFalse(Expense.objects.filter(description="Dépense supérieure aux ventes").exists())
