# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    zvy_is_commission_item = fields.Boolean(
        string='Commission Item',
        help='Purchases in this category are routed to the Holding Commission when quotes are approved.',
    )
