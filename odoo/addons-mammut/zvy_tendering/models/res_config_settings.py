# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    zvy_high_value_threshold = fields.Monetary(
        related='company_id.zvy_high_value_threshold',
        string='High-Value Threshold',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_default_bid_window_hours = fields.Integer(
        related='company_id.zvy_default_bid_window_hours',
        string='Default Bid Window (Hours)',
        readonly=False,
    )
    zvy_signatory_approval_category_id = fields.Many2one(
        related='company_id.zvy_signatory_approval_category_id',
        string='Signatory Approval Category',
        readonly=False,
    )
    zvy_sole_source_approver_ids = fields.Many2many(
        related='company_id.zvy_sole_source_approver_ids',
        string='Sole-Source Approvers',
        readonly=False,
    )
