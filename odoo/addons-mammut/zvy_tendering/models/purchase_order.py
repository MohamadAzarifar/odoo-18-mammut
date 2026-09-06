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


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    zvy_purchase_request_line_id = fields.Many2one(
        'zvy.purchase.request.line',
        string='Purchase Request Line',
        copy=False,
        index=True,
        ondelete='set null',
    )
