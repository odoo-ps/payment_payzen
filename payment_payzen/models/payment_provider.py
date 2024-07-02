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

class AcquirerPayzen(models.Model):
    _inherit = 'payment.acquirer'

    def _get_notify_url(self):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        return urlparse.urljoin(base_url, PayzenController._notify_url)

    def _get_languages(self):
        languages = constants.PAYZEN_LANGUAGES
        return [(c, _(l)) for c, l in languages.items()]

    @api.depends('provider')
    def _payzen_compute_multi_warning(self):
        for acquirer in self:
            acquirer.payzen_multi_warning = (constants.PAYZEN_PLUGIN_FEATURES.get('restrictmulti') == True) if (acquirer.provider == 'payzenmulti') else False

    sign_algo_help = _('Algorithm used to compute the payment form signature. Selected algorithm must be the same as one configured in the PayZen Back Office.')

    if constants.PAYZEN_PLUGIN_FEATURES.get('shatwo') == False:
        sign_algo_help += _('The HMAC-SHA-256 algorithm should not be activated if it is not yet available in the PayZen Back Office, the feature will be available soon.')

    # Compatibility with Odoo 14.
    payzen_odoo14 = parse_version(release.version) >= parse_version('14')

    providers = [('payzen', _('PayZen - Standard payment'))]
    if payzen_odoo14:
        ondelete_policy = {'payzen': 'set default'}

    if constants.PAYZEN_PLUGIN_FEATURES.get('multi') == True:
        providers.append(('payzenmulti', _('PayZen - Payment in installments')))
        if payzen_odoo14:
            ondelete_policy['payzenmulti'] = 'set default'

    if payzen_odoo14:
        provider = fields.Selection(selection_add=providers, ondelete = ondelete_policy)
    else:
        provider = fields.Selection(selection_add=providers)

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
    payzen_threeds_min_amount = fields.Char(string=_('Disable 3DS'), help=_('Amount below which 3DS will be disabled. Needs subscription to selective 3DS option. For more information, refer to the module documentation.'))
    payzen_redirect_enabled = fields.Selection(string=_('Automatic redirection'), help=_('If enabled, the buyer is automatically redirected to your site at the end of the payment.'), selection=[('0', _('Disabled')), ('1', _('Enabled'))])
    payzen_redirect_success_timeout = fields.Char(string=_('Redirection timeout on success'), help=_('Time in seconds (0-300) before the buyer is automatically redirected to your website after a successful payment.'))
    payzen_redirect_success_message = fields.Char(string=_('Redirection message on success'), help=_('Message displayed on the payment page prior to redirection after a successful payment.'), default=_('Redirection to shop in a few seconds...'))
    payzen_redirect_error_timeout = fields.Char(string=_('Redirection timeout on failure'), help=_('Time in seconds (0-300) before the buyer is automatically redirected to your website after a declined payment.'))
    payzen_redirect_error_message = fields.Char(string=_('Redirection message on failure'), help=_('Message displayed on the payment page prior to redirection after a declined payment.'), default=_('Redirection to shop in a few seconds...'))
    payzen_return_mode = fields.Selection(string=_('Return mode'), help=_('Method that will be used for transmitting the payment result from the payment page to your shop.'), selection=[('GET', 'GET'), ('POST', 'POST')])
    payzen_multi_warning = fields.Boolean(compute='_payzen_compute_multi_warning')

    payzen_multi_count = fields.Char(string=_('Count'), help=_('Total number of payments.'))
    payzen_multi_period = fields.Char(string=_('Period'), help=_('Delay (in days) between payments.'))
    payzen_multi_first = fields.Char(string=_('1st payment'), help=_('Amount of first payment, in percentage of total amount. If empty, all payments will have the same amount.'))

    is_for_payments_dd = fields.Boolean(string='Use for Payments Dropdown')
    
    # Check if it's Odoo 10.
    payzen_odoo10 = True if parse_version(release.version) < parse_version('11') else False

    # Compatibility betwen Odoo 13 and previous versions.
    payzen_odoo13 = True if parse_version(release.version) >= parse_version('13') else False

    if payzen_odoo13:
        image = fields.Char()
        environment = fields.Char()
    else:
        image_128 = fields.Char()
        state = fields.Char()

    payzen_redirect = False

    @api.model
    def multi_add(self, filename):
        file = path.join(path.dirname(path.dirname(path.abspath(__file__)))) + filename

        if (constants.PAYZEN_PLUGIN_FEATURES.get('multi') == True):
            convert_xml_import(self._cr, 'payment_payzen', file)

        return None

    def _get_ctx_mode(self):
        ctx_key = self.state if self.payzen_odoo13 else self.environment
        ctx_value = 'TEST' if ctx_key == 'test' else 'PRODUCTION'

        return ctx_value

    def _payzen_generate_sign(self, acquirer, values):
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
        if self.provider == 'payzenmulti':
            if (self.payzen_multi_first):
                first = int(float(self.payzen_multi_first) / 100 * int(amount))
            else:
                first = int(float(amount) / float(self.payzen_multi_count))

            payment_config = u'MULTI:first=' + str(first) + u';count=' + self.payzen_multi_count + u';period=' + self.payzen_multi_period
        else:
            payment_config = u'SINGLE'

        return payment_config

    def payzen_form_generate_values(self, values):
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')

        # trans_id is the number of 1/10 seconds from midnight.
        now = datetime.now()
        midnight = now.replace(hour = 0, minute = 0, second = 0, microsecond = 0)
        delta = int((now - midnight).total_seconds() * 10)
        trans_id = str(delta).rjust(6, '0')

        threeds_mpi = u''
        if self.payzen_threeds_min_amount and float(self.payzen_threeds_min_amount) > values['amount']:
            threeds_mpi = u'2'

        # Check currency.
        currency_num = tools.find_currency(values['currency'].name)
        if currency_num is None:
            _logger.error('The plugin cannot find a numeric code for the current shop currency {}.'.format(values['currency'].name))
            raise ValidationError(_('The shop currency {} is not supported.').format(values['currency'].name))

        # Amount in cents.
        k = int(values['currency'].decimal_places)
        amount = int(float_round(float_round(values['amount'], k) * (10 ** k), 0))

        # List of available languages.
        available_languages = ''
        for value in self.payzen_available_languages:
            available_languages += value.code + ';'

        # List of available payment cards.
        payment_cards = ''
        for value in self.payzen_payment_cards:
            payment_cards += value.code + ';'

        #Validation mode
        validation_mode = self.payzen_validation_mode if self.payzen_validation_mode != '-1' else ''

        # Enable redirection?
        AcquirerPayzen.payzen_redirect = str(self.payzen_redirect_enabled) == '1'

        reference = values.get('reference')
        if not reference:
            raise ValidationError('Missing value for "reference"') 
        reference = str(reference)

        tx_values = dict() # Values to sign in unicode.
        tx_values.update({
            'vads_site_id': self.payzen_site_id,
            'vads_amount': str(amount),
            'vads_sub_desc': u'',
            'vads_sub_amount': u'',
            'vads_sub_effect_date': u'',
            'vads_currency': currency_num,
            'vads_sub_currency': currency_num,
            'vads_trans_date': str(datetime.utcnow().strftime("%Y%m%d%H%M%S")),
            'vads_sub_init_amount_number': u'',
            'vads_sub_init_amount': u'',
            'vads_trans_id': str(trans_id),
            'vads_ctx_mode': str(self._get_ctx_mode()),
            'vads_page_action': u'PAYMENT',
            'vads_action_mode': u'INTERACTIVE',
            'vads_payment_config': self._get_payment_config(amount),
            'vads_version': constants.PAYZEN_PARAMS.get('GATEWAY_VERSION'),
            'vads_url_return': urlparse.urljoin(base_url, PayzenController._return_url),
            # 'vads_order_id': re.sub('[^a-zA-Z0-9\-]', '', reference),
            'vads_order_id': reference,
            'vads_contrib': constants.PAYZEN_PARAMS.get('CMS_IDENTIFIER') + u'_' + constants.PAYZEN_PARAMS.get('PLUGIN_VERSION') + u'/' + release.version,

            'vads_language': self.payzen_language or '',
            'vads_available_languages': available_languages,
            'vads_capture_delay': self.payzen_capture_delay or '',
            'vads_validation_mode': validation_mode,
            'vads_payment_cards': payment_cards,
            'vads_return_mode': str(self.payzen_return_mode),
            'vads_threeds_mpi': threeds_mpi,

            # Customer info.
            'vads_cust_id': str(values.get('billing_partner_id')) or '',
            'vads_cust_first_name': values.get('billing_partner_first_name') and values.get('billing_partner_first_name')[0:62] or '',
            'vads_cust_last_name': values.get('billing_partner_last_name') and values.get('billing_partner_last_name')[0:62] or '',
            'vads_cust_address': values.get('billing_partner_address') and values.get('billing_partner_address')[0:254] or '',
            'vads_cust_zip': values.get('billing_partner_zip') and values.get('billing_partner_zip')[0:62] or '',
            'vads_cust_city': values.get('billing_partner_city') and values.get('billing_partner_city')[0:62] or '',
            'vads_cust_state': values.get('billing_partner_state').code and values.get('billing_partner_state').code[0:62] or '',
            'vads_cust_country': values.get('billing_partner_country').code and values.get('billing_partner_country').code.upper() or '',
            'vads_cust_email': values.get('billing_partner_email') and values.get('billing_partner_email')[0:126] or '',
            'vads_cust_phone': values.get('billing_partner_phone') and values.get('billing_partner_phone')[0:31] or '',

            # Shipping info.
            'vads_ship_to_first_name': values.get('partner_first_name') and values.get('partner_first_name')[0:62] or '',
            'vads_ship_to_last_name': values.get('partner_last_name') and values.get('partner_last_name')[0:62] or '',
            'vads_ship_to_street': values.get('partner_address') and values.get('partner_address')[0:254] or '',
            'vads_ship_to_zip': values.get('partner_zip') and values.get('partner_zip')[0:62] or '',
            'vads_ship_to_city': values.get('partner_city') and values.get('partner_city')[0:62] or '',
            'vads_ship_to_state': values.get('partner_state').code and values.get('partner_state').code[0:62] or '',
            'vads_ship_to_country': values.get('partner_country').code and values.get('partner_country').code.upper() or '',
            'vads_ship_to_phone_num': values.get('partner_phone') and values.get('partner_phone')[0:31] or '',
        })
        
        reference = reference[:reference.index('x') if 'x' in reference else len(reference)]
        so = self.env['sale.order'].search([('name', '=', reference)], limit=1)
        if so and so.payment_acquier_id:
            if self.provider == 'payzenmulti':
                tx_values = self._alter_with_so_data(tx_values, so, amount)
            if so.partner_id.customer_nbr:
                tx_values.update({'vads_cust_id': str(so.partner_id.customer_nbr)})

        if AcquirerPayzen.payzen_redirect:
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

        payzen_tx_values['payzen_signature'] = self._payzen_generate_sign(self, tx_values)
        return payzen_tx_values

    def payzenmulti_form_generate_values(self, values):
        return self.payzen_form_generate_values(values)

    def payzen_get_form_action_url(self):
        return self.payzen_gateway_url

    def payzenmulti_get_form_action_url(self):
        return self.payzen_gateway_url

    def _alter_with_so_data(self, tx_values, so, amount):
        has_first_payment = True
        if not so.first_payment_amount and not so.first_payment_amount_mail:
            has_first_payment = False

        sec_date = so.second_payment_date or (so.date_order + relativedelta(months=+1)).date()
        vads_sub_desc = 'RRULE:FREQ=MONTHLY;'
        bymonthday = f'BYMONTHDAY={sec_date.day};'
        if sec_date.day > 28:
            bymonthday = u'BYMONTHDAY=28,29,30,31;BYSETPOS=-1;'
        vads_sub_desc += bymonthday
        if has_first_payment:
            vads_sub_desc += f'COUNT={int(self.payzen_multi_count)-1};'
            first_date = so.date_order
            today = date.today()
            capture_delay = abs((first_date.date() - today).days)
            sub_effect_date = datetime.combine(sec_date, datetime.min.time())

            if so.first_sub_payment_amount_mail:
                tx_values.update({
                    'vads_sub_init_amount_number': u'1',
                    'vads_sub_init_amount': str(int(so.first_sub_payment_amount_mail * 100))
                })
            tx_values.update({
                'vads_sub_desc': vads_sub_desc,
                'vads_page_action': u'REGISTER_PAY_SUBSCRIBE',
                'vads_amount': str(int(so.first_payment_amount_mail * 100)),
                'vads_payment_config': u'SINGLE',
                'vads_sub_amount': str(int(so.payzen_payment_monthly_amount * 100)),
                'vads_sub_effect_date': sub_effect_date.strftime('%Y%m%d'),
                'vads_capture_delay': str(capture_delay)
            })
        else:
            vads_sub_desc += u'COUNT=' + str(self.payzen_multi_count) + u';'
            if so.first_sub_payment_amount_mail:
                tx_values.update({
                    'vads_amount': str(int(so.first_sub_payment_amount_mail * 100)),
                    'vads_sub_init_amount_number': u'1',
                    'vads_sub_init_amount': str(int(so.first_sub_payment_amount_mail * 100))
                })
            else:
                tx_values.update({
                    'vads_amount': str(int(so.payzen_payment_monthly_amount * 100))
                })
            tx_values.update({
                'vads_sub_desc': vads_sub_desc,
                'vads_page_action': u'REGISTER_SUBSCRIBE',
                'vads_sub_amount': str(int(so.payzen_payment_monthly_amount * 100)),
                'vads_sub_effect_date': so.date_order.strftime('%Y%m%d')
            })
        
        _logger.info('tx_values : ')
        _logger.info(tx_values)
        return tx_values
