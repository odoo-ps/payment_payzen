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
            first, monthly = self._get_payments_so()
            amount = sale.amount_total * 100
            if first + (monthly * int(int(sale.payment_acquier_id.payzen_multi_count) - 1)) != amount:
                first_sub_amount = (amount - first) - (monthly * int(int(sale.payment_acquier_id.payzen_multi_count) - 2))
                sale.first_sub_payment_amount_mail = first_sub_amount / 100
            else:
                sale.first_sub_payment_amount_mail = 0
                

    @api.onchange('first_payment_amount')
    def _do_recompute(self):
        self.ensure_one()
        self.recompute()

    def _get_payments_so(self):
        self.ensure_one()
        if self.first_payment_amount:
            first = self.first_payment_amount_mail = self.first_payment_amount
            rest = int(100 * round((self.amount_total - first) % (int(self.payment_acquier_id.payzen_multi_count)-1 or 1), 2))
            monthly = ((self.amount_total - first) * 100  - rest) / (int(self.payment_acquier_id.payzen_multi_count)-1 or 1)
            first *= 100
        else:
            rest = int(100 * round(self.amount_total % (int(self.payment_acquier_id.payzen_multi_count) or 1), 2))
            monthly = (self.amount_total * 100 - rest) / (int(self.payment_acquier_id.payzen_multi_count) or 1)
            first = monthly + rest
            self.first_payment_amount_mail = 0
            if first != monthly:
                self.first_payment_amount_mail = first / 100
            # remove two next lines to activate again REGISTER_SUBSCRIBE mode
            else:
                self.first_payment_amount_mail = monthly / 100
        self.payzen_payment_monthly_amount = monthly / 100
        return first, monthly
    
    def get_mail_url(self):
        return self._get_share_url()

    def _prepare_confirmation_values(self):

        return {
            'state': 'sale',
        }
