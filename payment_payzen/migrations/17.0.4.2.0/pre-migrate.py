from odoo.upgrade import util


def migrate(cr, version):
    util.rename_field(cr, "sale.order", "recurring_payment_provider_id", "allowed_payment_provider_id")
    # remove fr translation to *actually* update it from .po
    cr.execute(
        """
        UPDATE ir_model_fields
        SET    field_description = field_description - 'fr_BE'
        WHERE  model = 'sale.order' AND name = 'allowed_payment_provider_id';
        """
    )
