# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    zvy_high_value_threshold = fields.Monetary(
        string='High-Value Threshold',
        currency_field='currency_id',
        help='Purchase requests with total at or above this amount are routed to the Holding Commission.',
    )
    zvy_default_bid_window_hours = fields.Integer(
        string='Default Bid Window (Hours)',
        default=72,
        help='Default hours from list approval to bid deadline for closed-envelope tenders.',
    )
    zvy_signatory_approval_category_id = fields.Many2one(
        'approval.category',
        string='Signatory Approval Category',
        help='Approval category used for sequential company signatory documents.',
    )
    zvy_sole_source_approver_ids = fields.Many2many(
        'res.users',
        'zvy_company_sole_source_approver_rel',
        'company_id',
        'user_id',
        string='Sole-Source Approvers',
        help='Users (e.g. CEO) required in the signatory chain for sole-source PRs (FR-14).',
    )
