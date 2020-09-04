# coding: utf-8

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_acquier_id = fields.Many2one('payment.acquirer', string="Payment Acquirer")
    second_payment_date = fields.Date('Second payment date')
    first_payment_amount = fields.Monetary('First amount to pay')
    payzen_get_months = fields.Integer(compute='_on_payment_acquier_id')
    first_payment_amount_mail = fields.Monetary(compute='_get_payzen_amounts')
    first_sub_payment_amount_mail = fields.Monetary(compute='_get_payzen_amounts')
    payzen_payment_monthly_amount = fields.Monetary(compute='_get_payzen_amounts')

    @api.onchange('order_line')
    def _onchange_order_line(self):
        self.ensure_one()
        booking_fee_qty = 0
        for line in self.order_line:
            if not line.product_id.product_tmpl_id.is_booking_fee and line.product_id.product_tmpl_id.evaluation_template_id:
                booking_fee_qty += line.product_uom_qty
        booking_fee_product = self.order_line.filtered(lambda x: x.product_id.product_tmpl_id.is_booking_fee is True)
        if booking_fee_product and booking_fee_product[0].product_uom_qty is not booking_fee_qty:
            booking_fee_product[0].product_uom_qty = booking_fee_qty

    @api.depends('payment_acquier_id')
    def _on_payment_acquier_id(self):
        for r in self:
            if r.payment_acquier_id:
                r.payzen_get_months = r.payment_acquier_id.payzen_multi_count

    @api.depends('payment_acquier_id', 'amount_total')
    def _get_payzen_amounts(self):
        for sale in self:
            if sale.first_payment_amount:
                sale.first_payment_amount_mail = sale.first_payment_amount
            first, monthly = sale._get_payzen_amounts()
            amount = sale.amount_total * 100
            sale.payzen_payment_monthly_amount = monthly
            if first + (monthly * int(int(sale.payment_acquier_id.payzen_multi_count) - 1)) != amount:
                first_sub_amount = (amount - first) - (monthly * int(int(sale.payment_acquier_id.payzen_multi_count) - 2))
                sale.first_sub_payment_amount_mail = first_sub_amount / 100


    @api.onchange('first_payment_amount')
    def _do_recompute(self):
        self.ensure_one()
        self.recompute()

    def _get_payments_so(self):
        self.ensure_one()
        first = int(self.first_payment_amount_mail * 100)
        monthly = int(round((self.amount_total * 100 - first) / (int(self.payment_acquier_id.payzen_multi_count) - 1)))
        return first, monthly
