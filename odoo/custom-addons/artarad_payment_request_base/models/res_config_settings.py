# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"


    module_artarad_payment_request_purchase = fields.Boolean()
    module_artarad_payment_request_payslip = fields.Boolean()
    module_artarad_payment_request_expense = fields.Boolean()
    module_artarad_payment_request_bill = fields.Boolean()
    module_artarad_payment_request_purchase_requisition = fields.Boolean()