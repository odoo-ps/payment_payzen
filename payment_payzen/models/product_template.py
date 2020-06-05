# coding: utf-8

from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_booking_fee = fields.Boolean('Booking fee')
