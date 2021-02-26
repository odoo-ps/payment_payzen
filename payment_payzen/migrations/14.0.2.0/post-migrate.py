# -*- coding: utf-8 -*-
from odoo.addons.ascor import util

import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):

    cr.execute("SELECT latest_version FROM ir_module_module WHERE name='base'")
    util.ENVIRON["__base_version"] = util.parse_version(cr.fetchone()[0])

    cr.execute("SELECT count(*) as total FROM ir_module_module WHERE demo='True'")
    if str(cr.fetchone()[0]) != '0':
        _logger.info('En dev ! Exit migration ')
        return

    _logger.info('###################################################################################')
    _logger.info('Begin post_migrate')

    _logger.info('Activate view')
    views_to_activate = [
            'payment_payzen.sale_view_form_custo'
    ]

    for view in views_to_activate:
        view_id = util.ref(cr,view)
        if view_id:
            cr.execute("Update ir_ui_view set active = 't' where id =%s", [view_id])



