# coding: utf-8

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_acquier_id = fields.Many2one('payment.acquirer', string="Payment Acquirer")
    second_payment_date = fields.Date('Second payment date')
    first_payment_amount = fields.Monetary('First amount to pay')
    payzen_get_months = fields.Integer(compute='_on_payment_acquier_id')
    first_payment_amount_mail = fields.Monetary()
    first_sub_payment_amount_mail = fields.Monetary()
    payzen_payment_monthly_amount = fields.Monetary()

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
