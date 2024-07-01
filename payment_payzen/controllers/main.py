# coding: utf-8
#
# Copyright © Lyra Network.
# This file is part of PayZen plugin for Odoo. See COPYING.md for license details.
#
# Author:    Lyra Network (https://www.lyra.com)
# Copyright: Copyright © Lyra Network
# License:   http://www.gnu.org/licenses/agpl.html GNU Affero General Public License (AGPL v3)

import logging
import pprint

from pkg_resources import parse_version
import werkzeug

from odoo import http, release
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class PayzenController(http.Controller):
    _notify_url = '/payment/payzen/ipn'
    _return_url = '/payment/payzen/return'

    def _get_return_url(self, result, **pdt_data):
        return_url = pdt_data.pop('return_url', '')

        if not return_url:
            return_url = '/payment/process' if result else '/shop/cart'

        return return_url

    @http.route(
        _return_url, type='http', auth='public', methods=['POST', 'GET'], csrf=False,
        save_session=False
    )
    def payzen_return_from_checkout(self, **pdt_data):
        # Check payment result and create transaction.
        _logger.info('PayZen: entering _from_notification with data %s', pprint.pformat(pdt_data))

        try:
            # Check the origin of the notification
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('payzen', pdt_data)

            # Handle the notification data
            tx_sudo._handle_notification_data('payzen', pdt_data)
        except ValidationError:
            _logger.exception("PayZen: Unable to handle the return notification data; skipping to acknowledge.")

        return request.redirect('/payment/status')

    @http.route(_notify_url, type='http', auth='public', methods=['POST'], csrf=False,
        save_session=False
    )
    def payzen_ipn(self, **post):
        # Check payment result and create transaction.
        _logger.info('PayZen: entering IPN _get_tx_from_notification with post data %s', pprint.pformat(post))

        try:
            result = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('payzen', post)

            # Handle the notification data
            result._handle_notification_data('payzen', post)
        except ValidationError: #Acknowledge the notification to avoid getting spammed
            _logger.exception("PayZen: Unable to handle the IPN notification data; skipping to acknowledge.")
            return 'Bad request received.'

        return 'Accepted payment, order has been updated.' if result else 'Payment failure, order has been cancelled.'
