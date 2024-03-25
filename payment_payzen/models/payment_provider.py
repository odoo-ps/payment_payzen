# coding: utf-8
#
# Copyright © Lyra Network.
# This file is part of PayZen plugin for Odoo. See COPYING.md for license details.
#
# Author:    Lyra Network (https://www.lyra.com)
# Copyright: Copyright © Lyra Network
# License:   http://www.gnu.org/licenses/agpl.html GNU Affero General Public License (AGPL v3)

import base64
from datetime import datetime
from hashlib import sha1, sha256
import hmac
import logging
import math
from os import path

from pkg_resources import parse_version

from odoo import models, api, release, fields, _
from odoo.exceptions import ValidationError
from odoo.tools import convert_xml_import
from odoo.tools import float_round
from odoo.tools.float_utils import float_compare
from odoo.http import request

from ..controllers.main import PayzenController
from ..helpers import constants, tools
from .card import PayzenCard
from .language import PayzenLanguage
from odoo.addons.payment import utils as payment_utils

import urllib.parse as urlparse
import re

_logger = logging.getLogger(__name__)

class ProviderPayzen(models.Model):
    _inherit = 'payment.provider'

    def _get_notify_url(self):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        return urlparse.urljoin(base_url, PayzenController._notify_url)

    def _get_languages(self):
        languages = constants.PAYZEN_LANGUAGES
        return [(c, _(l)) for c, l in languages.items()]

    def _payzen_compute_multi_warning(self):
        for provider in self:
            provider.payzen_multi_warning = (constants.PAYZEN_PLUGIN_FEATURES.get('restrictmulti') == True) if (provider.code == 'payzenmulti') else False

    def payzen_get_doc_field_value():
        docs_uri = constants.PAYZEN_ONLINE_DOC_URI
        doc_field_html = ''
        for lang, doc_uri in docs_uri.items():
            html = '<a href="%s%s">%s</a> '%(doc_uri,'odoo16/sitemap.html', constants.PAYZEN_DOCUMENTATION.get(lang))
            doc_field_html += html

        return doc_field_html

    sign_algo_help = _('Algorithm used to compute the payment form signature. Selected algorithm must be the same as one configured in the PayZen Back Office.')

    if constants.PAYZEN_PLUGIN_FEATURES.get('shatwo') == False:
        sign_algo_help += _('The HMAC-SHA-256 algorithm should not be activated if it is not yet available in the PayZen Back Office, the feature will be available soon.')

    providers = [('payzen', _('PayZen - Standard payment'))]
    ondelete_policy = {'payzen': 'set default'}

    if constants.PAYZEN_PLUGIN_FEATURES.get('multi') == True:
        providers.append(('payzenmulti', _('PayZen - Payment in installments')))
        ondelete_policy['payzenmulti'] = 'set default'

    code = fields.Selection(selection_add=providers, ondelete = ondelete_policy)

    payzen_doc = fields.Html(string=_('Click to view the module configuration documentation'), default=payzen_get_doc_field_value(), readonly=True)
    payzen_site_id = fields.Char(string=_('Shop ID'), help=_('The identifier provided by PayZen.'), default=constants.PAYZEN_PARAMS.get('SITE_ID'))
    payzen_key_test = fields.Char(string=_('Key in test mode'), help=_('Key provided by PayZen for test mode (available in PayZen Back Office).'), default=constants.PAYZEN_PARAMS.get('KEY_TEST'), readonly=constants.PAYZEN_PLUGIN_FEATURES.get('qualif'))
    payzen_key_prod = fields.Char(string=_('Key in production mode'), help=_('Key provided by PayZen (available in PayZen Back Office after enabling production mode).'), default=constants.PAYZEN_PARAMS.get('KEY_PROD'))
    payzen_sign_algo = fields.Selection(string=_('Signature algorithm'), help=sign_algo_help, selection=[('SHA-1', 'SHA-1'), ('SHA-256', 'HMAC-SHA-256')], default=constants.PAYZEN_PARAMS.get('SIGN_ALGO'))
    payzen_notify_url = fields.Char(string=_('Instant Payment Notification URL'), help=_('URL to copy into your PayZen Back Office > Settings > Notification rules.'), default=_get_notify_url, readonly=True)
    payzen_gateway_url = fields.Char(string=_('Payment page URL'), help=_('Link to the payment page.'), default=constants.PAYZEN_PARAMS.get('GATEWAY_URL'))
    payzen_language = fields.Selection(string=_('Default language'), help=_('Default language on the payment page.'), default=constants.PAYZEN_PARAMS.get('LANGUAGE'), selection=_get_languages)
    payzen_available_languages = fields.Many2many('payzen.language', string=_('Available languages'), column1='code', column2='label', help=_('Languages available on the payment page. If you do not select any, all the supported languages will be available.'))
    payzen_capture_delay = fields.Char(string=_('Capture delay'), help=_('The number of days before the bank capture (adjustable in your PayZen Back Office).'))
    payzen_validation_mode = fields.Selection(string=_('Validation mode'), help=_('If manual is selected, you will have to confirm payments manually in your PayZen Back Office.'), selection=[('-1', _('PayZen Back Office Configuration')), ('0', _('Automatic')), ('1', _('Manual'))])
    payzen_payment_cards = fields.Many2many('payzen.card', string=_('Card types'), column1='code', column2='label', help=_('The card type(s) that can be used for the payment. Select none to use gateway configuration.'))
    payzen_threeds_min_amount = fields.Char(string=_('Manage 3DS'), help=_('Amount below which customer could be exempt from strong authentication. Needs subscription to «Selective 3DS1» or «Frictionless 3DS2» options. For more information, refer to the module documentation.'))
    payzen_redirect_enabled = fields.Selection(string=_('Automatic redirection'), help=_('If enabled, the buyer is automatically redirected to your site at the end of the payment.'), selection=[('0', _('Disabled')), ('1', _('Enabled'))])
    payzen_redirect_success_timeout = fields.Char(string=_('Redirection timeout on success'), help=_('Time in seconds (0-300) before the buyer is automatically redirected to your website after a successful payment.'))
    payzen_redirect_success_message = fields.Char(string=_('Redirection message on success'), help=_('Message displayed on the payment page prior to redirection after a successful payment.'), default=_('Redirection to shop in a few seconds...'))
    payzen_redirect_error_timeout = fields.Char(string=_('Redirection timeout on failure'), help=_('Time in seconds (0-300) before the buyer is automatically redirected to your website after a declined payment.'))
    payzen_redirect_error_message = fields.Char(string=_('Redirection message on failure'), help=_('Message displayed on the payment page prior to redirection after a declined payment.'), default=_('Redirection to shop in a few seconds...'))
    payzen_return_mode = fields.Selection(string=_('Return mode'), help=_('Method that will be used for transmitting the payment result from the payment page to your shop.'), selection=[('GET', 'GET'), ('POST', 'POST')])
    payzen_multi_warning = fields.Boolean(compute='_payzen_compute_multi_warning')

    payzen_multi_count = fields.Char(string=_('Count'), help=_('Installments number'))
    payzen_multi_period = fields.Char(string=_('Period'), help=_('Delay (in days) between installments.'))
    payzen_multi_first = fields.Char(string=_('1st installment'), help=_('Amount of first installment, in percentage of total amount. If empty, all installments will have the same amount.'))

    environment = fields.Char()

    payzen_redirect = False

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """ Override of payment to unlist PayZen providers when the currency is not supported. """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name and tools.find_currency(currency.name) is None:
            providers = providers.filtered(
                lambda p: p.code not in ['payzen', 'payzenmulti']
            )

        return providers

    @api.model
    def multi_add(self, filename):
        if (constants.PAYZEN_PLUGIN_FEATURES.get('multi') == True):
            file = path.join(path.dirname(path.dirname(path.abspath(__file__)))) + filename
            convert_xml_import(self.env, 'payment_payzen', file)

        return None

    def _get_ctx_mode(self):
        ctx_key = self.state
        ctx_value = 'TEST' if ctx_key == 'test' else 'PRODUCTION'

        return ctx_value

    def _payzen_generate_sign(self, provider, values):
        key = self.payzen_key_prod if self._get_ctx_mode() == 'PRODUCTION' else self.payzen_key_test

        sign = ''
        for k in sorted(values.keys()):
            if k.startswith('vads_'):
                sign += values[k] + '+'

        sign += key

        if self.payzen_sign_algo == 'SHA-1':
            shasign = sha1(sign.encode('utf-8')).hexdigest()
        else:
            shasign = base64.b64encode(hmac.new(key.encode('utf-8'), sign.encode('utf-8'), sha256).digest()).decode('utf-8')

        return shasign

    def _get_payment_config(self, amount):
        if self.code == 'payzenmulti':
            if (self.payzen_multi_first):
                first = int(float(self.payzen_multi_first) / 100 * int(amount))
            else:
                first = int(float(amount) / float(self.payzen_multi_count))

            payment_config = u'MULTI:first=' + str(first) + u';count=' + self.payzen_multi_count + u';period=' + self.payzen_multi_period
        else:
            payment_config = u'SINGLE'

        return payment_config

    def payzen_form_generate_values(self, values):
        base_url = request.httprequest.host_url

        # trans_id is the number of 1/10 seconds from midnight.
        now = datetime.now()
        midnight = now.replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        delta = int((now - midnight).total_seconds() * 10)
        trans_id = str(delta).rjust(6, '0')

        threeds_mpi = u''
        if self.payzen_threeds_min_amount and float(self.payzen_threeds_min_amount) > values['amount']:
            threeds_mpi = u'2'

        # Check currency.
        if 'currency' in values:
            currency = values['currency']
        else:
            currency = self.env['res.currency'].browse(values['currency_id']).exists()

        currency_num = tools.find_currency(currency.name)
        if currency_num is None:
            _logger.error('The plugin cannot find a numeric code for the current shop currency {}.'.format(currency.name))
            raise ValidationError(_('The shop currency {} is not supported.').format(currency.name))

        # Amount in cents.
        k = int(currency.decimal_places)
        amount = int(float_round(float_round(values['amount'], k) * (10 ** k), 0))

        # List of available languages.
        available_languages = ''
        for value in self.payzen_available_languages:
            available_languages += value.code + ';'

        # List of available payment cards.
        payment_cards = ''
        for value in self.payzen_payment_cards:
            payment_cards += value.code + ';'

        # Validation mode.
        validation_mode = self.payzen_validation_mode if self.payzen_validation_mode != '-1' else ''

        # Enable redirection?
        ProviderPayzen.payzen_redirect = True if str(self.payzen_redirect_enabled) == '1' else False

        order_id = re.sub("[^0-9a-zA-Z_-]+", "", values.get('reference'))

        tx_values = dict() # Values to sign in unicode.
        tx_values.update({
            'vads_site_id': self.payzen_site_id,
            'vads_amount': str(amount),
            'vads_currency': currency_num,
            'vads_trans_date': str(datetime.utcnow().strftime("%Y%m%d%H%M%S")),
            'vads_trans_id': str(trans_id),
            'vads_ctx_mode': str(self._get_ctx_mode()),
            'vads_page_action': u'PAYMENT',
            'vads_action_mode': u'INTERACTIVE',
            'vads_payment_config': self._get_payment_config(amount),
            'vads_version': constants.PAYZEN_PARAMS.get('GATEWAY_VERSION'),
            'vads_url_return': urlparse.urljoin(base_url, PayzenController._return_url),
            'vads_order_id': str(order_id),
            'vads_ext_info_order_ref': str(values.get('reference')),
            'vads_contrib': constants.PAYZEN_PARAMS.get('CMS_IDENTIFIER') + u'_' + constants.PAYZEN_PARAMS.get('PLUGIN_VERSION') + u'/' + release.version,

            'vads_language': self.payzen_language or '',
            'vads_available_languages': available_languages,
            'vads_capture_delay': self.payzen_capture_delay or '',
            'vads_validation_mode': validation_mode,
            'vads_payment_cards': payment_cards,
            'vads_return_mode': str(self.payzen_return_mode),
            'vads_threeds_mpi': threeds_mpi
        })

        if ProviderPayzen.payzen_redirect:
            tx_values.update({
                'vads_redirect_success_timeout': self.payzen_redirect_success_timeout or '',
                'vads_redirect_success_message': self.payzen_redirect_success_message or '',
                'vads_redirect_error_timeout': self.payzen_redirect_error_timeout or '',
                'vads_redirect_error_message': self.payzen_redirect_error_message or ''
            })

        payzen_tx_values = dict() # Values encoded in UTF-8.

        for key in tx_values.keys():
            if tx_values[key] == ' ':
                tx_values[key] = ''

            payzen_tx_values[key] = tx_values[key].encode('utf-8')

        return payzen_tx_values

    def payzen_get_form_action_url(self):
        return self.payzen_gateway_url

    def _get_default_payment_method_id(self, code):
        self.ensure_one()
        if self.code != 'payzen' and self.code != 'payzenmulti':
            return super()._get_default_payment_method_id(code)

        if self.code == 'payzen':
            return self.env.ref('payment_payzen.payment_method_payzen').id
        if self.code == 'payzenmulti':
            return self.env.ref('payment_payzen.payment_method_payzenmulti').id
