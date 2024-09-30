from odoo.tests import tagged
from odoo import Command

from odoo.addons.payment.tests.common import PaymentCommon
from odoo.addons.sale.tests.common import TestSaleCommon


@tagged("post_install", "-at_install")
class TestRecurringPayments(TestSaleCommon, PaymentCommon):
    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)

        cls.recurring_provider = cls._prepare_provider("payzenmulti")

        cls.sale_order = (
            cls.env["sale.order"]
            .with_context(tracking_disable=True)
            .create({
                "partner_id": cls.partner_a.id,
                "partner_invoice_id": cls.partner_a.id,
                "partner_shipping_id": cls.partner_a.id,
                "pricelist_id": cls.company_data["default_pricelist"].id,
                "allowed_payment_provider_id": cls.recurring_provider.id,
            })
        )
        cls.sale_order_line = cls.env["sale.order.line"].create({
            "order_id": cls.sale_order.id,
            "name": cls.company_data["product_order_no"].name,
            "product_id": cls.company_data["product_order_no"].id,
            "product_uom_qty": 1,
            "product_uom": cls.company_data["product_order_no"].uom_id.id,
            "price_unit": 0,
            "tax_id": False,
        })

    def test_recurring_payments(self):
        self.recurring_provider.payzen_multi_count = 5
        self.assertEqual(self.sale_order.recurring_payment_months, 5)
        self.sale_order_line.price_unit = 100
        self.sale_order.recurring_first_payment_amount_manual = None
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 20)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 20)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 20)

        self.recurring_provider.payzen_multi_count = 9
        self.assertEqual(self.sale_order.recurring_payment_months, 9)
        self.sale_order_line.price_unit = 250
        self.sale_order.recurring_first_payment_amount_manual = 50
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 50)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 25)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 25)

        self.recurring_provider.payzen_multi_count = 6
        self.assertEqual(self.sale_order.recurring_payment_months, 6)
        self.sale_order_line.price_unit = 80
        self.sale_order.recurring_first_payment_amount_manual = 30
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 30)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 10)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 10)

        self.recurring_provider.payzen_multi_count = 6
        self.assertEqual(self.sale_order.recurring_payment_months, 6)
        self.sale_order_line.price_unit = 84
        self.sale_order.recurring_first_payment_amount_manual = 30
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 30)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 14)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 10)

        self.recurring_provider.payzen_multi_count = 1
        self.assertEqual(self.sale_order.recurring_payment_months, 1)
        self.sale_order_line.price_unit = 55
        self.sale_order.recurring_first_payment_amount_manual = None
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 55)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 0)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 0)

        self.recurring_provider.payzen_multi_count = 1
        self.assertEqual(self.sale_order.recurring_payment_months, 1)
        self.sale_order_line.price_unit = 61
        self.sale_order.recurring_first_payment_amount_manual = 61
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 61)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 0)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 0)

        self.recurring_provider.payzen_multi_count = 0
        self.assertEqual(self.sale_order.recurring_payment_months, 0)
        self.sale_order_line.price_unit = 33
        self.sale_order.recurring_first_payment_amount_manual = None
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 33)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 0)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 0)

        self.recurring_provider.payzen_multi_count = 3
        self.assertEqual(self.sale_order.recurring_payment_months, 3)
        self.sale_order_line.price_unit = 20
        self.sale_order.recurring_first_payment_amount_manual = None
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 8)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 6)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 6)

        self.recurring_provider.payzen_multi_count = 2
        self.assertEqual(self.sale_order.recurring_payment_months, 2)
        self.sale_order_line.price_unit = 30
        self.sale_order.recurring_first_payment_amount_manual = None
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 15)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 15)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 15)

        self.recurring_provider.payzen_multi_count = 2
        self.assertEqual(self.sale_order.recurring_payment_months, 2)
        self.sale_order_line.price_unit = 40
        self.sale_order.recurring_first_payment_amount_manual = 30
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 30)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 10)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 10)

        self.recurring_provider.payzen_multi_count = 11
        self.assertEqual(self.sale_order.recurring_payment_months, 11)
        self.sale_order_line.price_unit = 151.55
        self.sale_order.recurring_first_payment_amount_manual = 50
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 50)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 11.55)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 10)

        self.recurring_provider.payzen_multi_count = 10
        self.assertEqual(self.sale_order.recurring_payment_months, 10)
        self.sale_order_line.price_unit = 138
        # Integer fields coerce None => 0, and therefore this acts like if first payment is not set (i.e. autocompute)
        self.sale_order.recurring_first_payment_amount_manual = 0
        self.assertEqual(self.sale_order.recurring_first_payment_amount, 21)
        self.assertEqual(self.sale_order.recurring_second_payment_amount, 13)
        self.assertEqual(self.sale_order.recurring_payment_monthly_amount, 13)
