# coding: utf-8
#
# Copyright © Lyra Network.
# This file is part of PayZen plugin for Odoo. See COPYING.md for license details.
#
# Author:    Lyra Network (https://www.lyra.com)
# Copyright: Copyright © Lyra Network
# License:   http://www.gnu.org/licenses/agpl.html GNU Affero General Public License (AGPL v3)

{
    'name': 'PayZen Payment Provider',
    'version': '17.0.4.0.0',
    'summary': 'Accept payments with PayZen secure payment gateway.',
    'category': 'Accounting/Payment Providers',
    'author': 'Lyra Network',
    'website': 'https://www.lyra.com/',
    'license': 'AGPL-3',
    'depends': ['payment', 'account', 'sale_management', 'sale', 'purchase', 'website_sale', 'product', 'ascor_training'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_payzen_templates.xml',
        'views/sale_order_views.xml',
        'views/product_template_views.xml',
        'templates/web_payment_template.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
        'security/ir.model.access.csv',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'images': ['static/description/icon.png'],
    'application': True,
    'installable': True
}
