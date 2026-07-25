# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _


class AccountPayment(models.Model):
    _inherit = "account.payment"

    
    request_id = fields.Many2one("artarad.account.payment.request")