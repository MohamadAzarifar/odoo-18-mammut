# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ZvyCommissionCase(models.Model):
    """Minimal shell for Phase 2 routing; full UX lands in Phase 3."""

    _name = 'zvy.commission.case'
    _description = 'Holding Commission Case'
    _order = 'id desc'

    name = fields.Char(
        string='Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
    )
    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='request_id.company_id',
        store=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('in_review', 'In Review'),
            ('meeting', 'Meeting'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('corrections', 'Corrections'),
        ],
        default='open',
        required=True,
        copy=False,
        index=True,
    )
    reason_high_value = fields.Boolean(string='Routed: High Value')
    reason_commission_item = fields.Boolean(string='Routed: Commission Item')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) in (False, _('New'), 'New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'zvy.commission.case'
                ) or _('New')
        return super().create(vals_list)
