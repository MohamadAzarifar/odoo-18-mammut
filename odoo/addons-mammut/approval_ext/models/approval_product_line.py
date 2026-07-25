# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line'

    approval_ext_product_category_ids = fields.Many2many(
        related='approval_request_id.category_id.approval_ext_product_category_ids',
    )
    approval_ext_product_id_domain = fields.Char(
        compute='_compute_approval_ext_product_id_domain',
    )

    @api.depends(
        'approval_request_id',
        'approval_request_id.category_id',
        'approval_request_id.category_id.approval_ext_product_category_ids',
    )
    def _compute_approval_ext_product_id_domain(self):
        for line in self:
            categories = line.approval_request_id.category_id.approval_ext_product_category_ids
            if categories:
                line.approval_ext_product_id_domain = str([
                    ('categ_id', 'child_of', categories.ids),
                ])
            else:
                line.approval_ext_product_id_domain = '[]'

    @api.constrains('product_id', 'approval_request_id')
    def _check_approval_ext_product_category(self):
        for line in self:
            if not line.product_id:
                continue
            categories = line.approval_request_id.category_id.approval_ext_product_category_ids
            if not categories:
                continue
            if not self.env['product.product'].search_count([
                ('id', '=', line.product_id.id),
                ('categ_id', 'child_of', categories.ids),
            ]):
                raise ValidationError(_(
                    'Product "%(product)s" is not in an allowed product category for '
                    'approval type "%(category)s".',
                    product=line.product_id.display_name,
                    category=line.approval_request_id.category_id.display_name,
                ))

    def _approval_ext_invalidate_request_approvers(self):
        requests = self.mapped('approval_request_id').filtered(
            lambda r: r.request_status in ('new', 'editing')
        )
        if requests:
            requests.invalidate_recordset([
                'approver_ids',
                'approval_ext_effective_minimum',
            ])

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._approval_ext_invalidate_request_approvers()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'product_id' in vals:
            self._approval_ext_invalidate_request_approvers()
        return res

    def unlink(self):
        requests = self.mapped('approval_request_id').filtered(
            lambda r: r.request_status in ('new', 'editing')
        )
        res = super().unlink()
        if requests:
            requests.invalidate_recordset([
                'approver_ids',
                'approval_ext_effective_minimum',
            ])
        return res