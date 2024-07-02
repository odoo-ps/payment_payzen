# coding: utf-8
#
# Copyright © Lyra Network.
# This file is part of PayZen plugin for Odoo. See COPYING.md for license details.
#
# Author:    Lyra Network (https://www.lyra.com)
# Copyright: Copyright © Lyra Network
# License:   http://www.gnu.org/licenses/agpl.html GNU Affero General Public License (AGPL v3)

import base64
from datetime import datetime, date
from hashlib import sha1, sha256
from dateutil.relativedelta import relativedelta
import hmac
import logging
import math
import re
from os import path

from pkg_resources import parse_version

from odoo import models, api, release, fields, _
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.tools import convert_xml_import
from odoo.tools import float_round
from odoo.tools.float_utils import float_compare

from ..controllers.main import PayzenController
from ..helpers import constants, tools
from .card import PayzenCard
from .language import PayzenLanguage


try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

_logger = logging.getLogger(__name__)

class TransactionPayzen(models.Model):
    _inherit = 'payment.transaction'

    payzen_trans_status = fields.Char(_('Transaction status'))
    payzen_card_brand = fields.Char(_('Means of payment'))
    payzen_card_number = fields.Char(_('Card number'))
    payzen_expiration_date = fields.Char(_('Expiration date'))
    payzen_auth_result = fields.Char(_('Authorization result'))
    payzen_raw_data = fields.Text(string=_('Transaction log'), readonly=True)

    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------

    @api.model
    def _payzen_form_get_tx_from_data(self, data):
        shasign, status, reference = data.get('signature'), data.get('vads_trans_status'), data.get('vads_order_id')

        if not reference or not shasign or not status:
            error_msg = 'PayZen : received bad data {}'.format(data)
            _logger.error(error_msg)
            raise ValidationError(error_msg)

        tx = self.search([('reference', '=', reference)])
        if not tx or len(tx) > 1:
            error_msg = 'PayZen: received data for reference {}'.format(reference)
            if not tx:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'

            _logger.error(error_msg)
            raise ValidationError(error_msg)

        # Verify shasign.
        shasign_check = tx.acquirer_id._payzen_generate_sign('out', data)
        if shasign_check.upper() != shasign.upper():
            error_msg = 'PayZen: invalid shasign, received {}, computed {}, for data {}'.format(shasign, shasign_check, data)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        return tx

    def _payzen_form_get_invalid_parameters(self, data):
        invalid_parameters = []

        # Check what is bought.
        # amount = float(int(data.get('vads_amount', 0)) / math.pow(10, int(self.currency_id.decimal_places)))

        # if float_compare(amount, self.amount, int(self.currency_id.decimal_places)) != 0:
        #     invalid_parameters.append(('amount', amount, '{:.2f}'.format(self.amount)))

        currency_code = tools.find_currency(self.currency_id.name)
        if (currency_code is None) or (int(data.get('vads_currency')) != int(currency_code)):
            invalid_parameters.append(('currency', data.get('vads_currency'), currency_code))

        return invalid_parameters

    def _payzen_form_validate(self, data):
        payzen_statuses = {
            'success': ['AUTHORISED', 'CAPTURED', 'ACCEPTED'],
            'pending': ['AUTHORISED_TO_VALIDATE', 'WAITING_AUTHORISATION', 'WAITING_AUTHORISATION_TO_VALIDATE', 'INITIAL', 'UNDER_VERIFICATION', 'WAITING_FOR_PAYMENT', 'PRE_AUTHORISED'],
            'cancel': ['ABANDONED']
        }

        html_3ds = _('3DS authentication: ')
        if data.get('vads_threeds_status') == 'Y':
            html_3ds += _('YES')
            html_3ds += '<br />' + _('3DS certificate: ') + data.get('vads_threeds_cavv')
        else:
            html_3ds += _('NO')

        expiry = ''
        if data.get('vads_expiry_month') and data.get('vads_expiry_year'):
            expiry = data.get('vads_expiry_month').zfill(2) + '/' + data.get('vads_expiry_year')

        values = {
            'acquirer_reference': data.get('vads_trans_uuid'),
            'payzen_raw_data': '{}'.format(data),
            'html_3ds': html_3ds,
            'payzen_trans_status': data.get('vads_trans_status'),
            'payzen_card_brand': data.get('vads_card_brand'),
            'payzen_card_number': data.get('vads_card_number'),
            'payzen_expiration_date': expiry,
        }

        # Set validation date.
        key = 'date' if hasattr(self, 'date')  else 'date_validate'
        values[key] = fields.Datetime.now()

        status = data.get('vads_trans_status')
        if status in payzen_statuses['success']:
            values.update({
                'state': 'done',
            })

            self.write(values)

            return True
        elif status in payzen_statuses['pending']:
            values.update({
                'state': 'pending',
            })

            self.write(values)

            return True
        elif status in payzen_statuses['cancel']:
            self.write({
                'state_message': 'Payment for transaction #%s is cancelled (%s).' % (self.reference, data.get('vads_result')),
                'state': 'cancel',
            })

            return False
        else:
            auth_result = data.get('vads_auth_result')
            auth_message = _('See the transaction details for more information ({}).').format(auth_result)

            error_msg = 'PayZen payment error, transaction status: {}, authorization result: {}.'.format(status, auth_result)
            _logger.info(error_msg)

            values.update({
                'state_message': 'Payment for transaction #%s is refused (%s).' % (self.reference, data.get('vads_result')),
                'state': 'error',
                'payzen_auth_result': auth_message,
            })

            self.write(values)

            return False

    @api.model
    def _compute_reference(self, values=None, prefix=None):
        res = super()._compute_reference(values=values, prefix=prefix)
        acquirer = self.env['payment.acquirer'].browse(values.get('acquirer_id'))
        if acquirer and acquirer.provider == 'payzenmulti':
            reference = res[:res.index('-') if '-' in res else len(res)]
            n = self.env['payment.transaction'].sudo().search_count([('reference', 'like', reference)])
            if n:
                reference += f"x{n}"
            return reference
        return res