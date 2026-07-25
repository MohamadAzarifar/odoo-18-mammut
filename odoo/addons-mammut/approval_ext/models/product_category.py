# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    required_approver_user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='product_category_required_approver_user_rel',
        column1='category_id',
        column2='user_id',
        string='Required approval users',
        groups='approvals.group_approval_manager',
        help='Users who must approve requests that include products from this category.',
    )
