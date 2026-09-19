# -*- coding: utf-8 -*-
from odoo import api, fields, models


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
    zvy_company_scale = fields.Selection(
        related='company_id.zvy_company_scale',
        string='Company Scale',
        readonly=False,
    )
    zvy_use_custom_bands = fields.Boolean(
        related='company_id.zvy_use_custom_bands',
        string='Override Purchase-Level Bands',
        readonly=False,
    )
    zvy_op_minor_max = fields.Monetary(
        related='company_id.zvy_op_minor_max',
        string='Operational Minor Max',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_op_medium_max = fields.Monetary(
        related='company_id.zvy_op_medium_max',
        string='Operational Medium Max',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_op_major_max = fields.Monetary(
        related='company_id.zvy_op_major_max',
        string='Operational Major Max',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_op_large_ceo_max = fields.Monetary(
        related='company_id.zvy_op_large_ceo_max',
        string='Operational Large CEO Max',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_nop_minor_max = fields.Monetary(
        related='company_id.zvy_nop_minor_max',
        string='Non-Operational Minor Max',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_nop_medium_max = fields.Monetary(
        related='company_id.zvy_nop_medium_max',
        string='Non-Operational Medium Max',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_nop_major_max = fields.Monetary(
        related='company_id.zvy_nop_major_max',
        string='Non-Operational Major Max',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_nop_large_ceo_max = fields.Monetary(
        related='company_id.zvy_nop_large_ceo_max',
        string='Non-Operational Large CEO Max',
        readonly=False,
        currency_field='company_currency_id',
    )
    zvy_signatory_minor_job_id = fields.Many2one(
        related='company_id.zvy_signatory_minor_job_id',
        string='Minor Signatory Job',
        readonly=False,
    )
    zvy_signatory_medium_job_id = fields.Many2one(
        related='company_id.zvy_signatory_medium_job_id',
        string='Medium Signatory Job',
        readonly=False,
    )
    zvy_signatory_major_job_id = fields.Many2one(
        related='company_id.zvy_signatory_major_job_id',
        string='Major Signatory Job',
        readonly=False,
    )
    zvy_signatory_large_job_id = fields.Many2one(
        related='company_id.zvy_signatory_large_job_id',
        string='Large Signatory Job',
        readonly=False,
    )
    zvy_signatory_board_job_id = fields.Many2one(
        related='company_id.zvy_signatory_board_job_id',
        string='Board Signatory Job',
        readonly=False,
    )
    zvy_signatory_formalities_job_id = fields.Many2one(
        related='company_id.zvy_signatory_formalities_job_id',
        string='Formalities Signatory Job',
        readonly=False,
    )
    zvy_is_holding_company = fields.Boolean(
        compute='_compute_zvy_is_holding_company',
    )
    zvy_commission_notice_days = fields.Integer(
        related='company_id.root_id.zvy_commission_notice_days',
        string='Commission Notice Days',
        readonly=False,
    )
    zvy_commission_require_proforma = fields.Boolean(
        related='company_id.root_id.zvy_commission_require_proforma',
        string='Require Awarded Proforma',
        readonly=False,
    )
    zvy_commission_require_comparison = fields.Boolean(
        related='company_id.root_id.zvy_commission_require_comparison',
        string='Require Comparison Document',
        readonly=False,
    )
    zvy_commission_require_technical = fields.Boolean(
        related='company_id.root_id.zvy_commission_require_technical',
        string='Require Technical Request',
        readonly=False,
    )

    @api.depends('company_id', 'company_id.root_id')
    def _compute_zvy_is_holding_company(self):
        for rec in self:
            company = rec.company_id
            rec.zvy_is_holding_company = bool(company) and company == company._zvy_holding_company()
