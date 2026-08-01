# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    zvy_purchase_request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        copy=False,
        index=True,
        ondelete='set null',
    )
