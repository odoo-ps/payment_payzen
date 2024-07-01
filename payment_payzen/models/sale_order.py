from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # TODO: rename again so that _mail is not used (maybe have first_payment_amount_override? or just inverse compute?)
    recurring_payment_provider_id = fields.Many2one("payment.provider", domain='[("support_recurring", "=", True)]')
    recurring_payment_months = fields.Integer(compute="_compute_recurring_payment_months")
    recurring_first_payment_amount = fields.Monetary("First amount to pay")
    recurring_first_payment_amount_mail = fields.Monetary(compute="_compute_payments_amounts")
    recurring_second_payment_amount_mail = fields.Monetary(compute="_compute_payments_amounts")
    recurring_second_payment_date = fields.Date("Second payment date")
    recurring_payment_monthly_amount = fields.Monetary(compute="_compute_payments_amounts")

    @api.depends("recurring_payment_provider_id.payzen_multi_count", "recurring_payment_provider_id.code")
    def _compute_recurring_payment_months(self):
        for order in self:
            if order.recurring_payment_provider_id:
                if order.recurring_payment_provider_id.code != "payzenmulti":
                    raise ValidationError(
                        _("Invalid payment provider for recurring payment: %s")
                        % (order.recurring_payment_provider_id.name)
                    )
                order.recurring_payment_months = order.recurring_payment_provider_id.payzen_multi_count
            else:
                order.recurring_payment_months = 0

    @api.depends("recurring_payment_months", "amount_total", "recurring_first_payment_amount")
    def _compute_payments_amounts(self):
        for order in self:
            first = None
            recurring_months = max(1, order.recurring_payment_months or 1)
            recurring_total = order.amount_total
            if order.recurring_first_payment_amount:
                first = order.recurring_first_payment_amount
                recurring_months -= 1
                recurring_total -= order.recurring_first_payment_amount
            remainder = order.currency_id.round(recurring_total % recurring_months)
            monthly = order.currency_id.round((recurring_total - remainder) / recurring_months)
            if first is None:
                first = monthly + remainder
                remainder = 0

            order.recurring_first_payment_amount_mail = first
            order.recurring_second_payment_amount_mail = monthly + remainder
            order.recurring_payment_monthly_amount = monthly

    def get_mail_url(self):
        return self._get_share_url()
