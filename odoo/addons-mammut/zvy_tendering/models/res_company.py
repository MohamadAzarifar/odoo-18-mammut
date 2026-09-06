# -*- coding: utf-8 -*-
from odoo import fields, models

from .zvy_purchase_bands import (
    ZVY_BAND_KEYS,
    ZVY_PURCHASE_BANDS,
    zvy_level_from_amount,
)


class ResCompany(models.Model):
    _inherit = 'res.company'

    zvy_high_value_threshold = fields.Monetary(
        string='High-Value Threshold',
        currency_field='currency_id',
        help='Deprecated. Unused for routing. Large purchase level qualifies '
             'for Holding Commission (enquiry after signatures, FR-35).',
    )
    zvy_default_bid_window_hours = fields.Integer(
        string='Default Bid Window (Hours)',
        default=72,
        help='Default hours from list approval to bid deadline for closed-envelope tenders.',
    )
    zvy_signatory_approval_category_id = fields.Many2one(
        'approval.category',
        string='Signatory Approval Category',
        help='Sequential approval category used as the signatory document '
             'template. Approver users come from the per-band lists, not '
             'from this category.',
    )
    zvy_sole_source_approver_ids = fields.Many2many(
        'res.users',
        'zvy_company_sole_source_approver_rel',
        'company_id',
        'user_id',
        string='Sole-Source Approvers',
        help='Users (e.g. CEO) required last in the signatory chain for '
             'sole-source PRs (FR-14).',
    )
    zvy_company_scale = fields.Selection(
        selection=[
            ('small', 'Small Scale'),
            ('medium', 'Medium Scale'),
            ('large', 'Large Scale'),
        ],
        string='Company Scale',
        default='small',
        required=True,
        help='Selects the R-PL purchase-level table (small / medium / large group companies).',
    )
    zvy_use_custom_bands = fields.Boolean(
        string='Override Purchase-Level Bands',
        help='When set, use the custom operational and non-operational '
             'ceilings below instead of the baked-in bylaws table.',
    )
    zvy_op_minor_max = fields.Monetary(
        string='Operational Minor Max',
        currency_field='currency_id',
    )
    zvy_op_medium_max = fields.Monetary(
        string='Operational Medium Max',
        currency_field='currency_id',
    )
    zvy_op_major_max = fields.Monetary(
        string='Operational Major Max',
        currency_field='currency_id',
    )
    zvy_op_large_ceo_max = fields.Monetary(
        string='Operational Large CEO Max',
        currency_field='currency_id',
        help='Within large operational purchases, CEO signs up to this amount; Board above it.',
    )
    zvy_nop_minor_max = fields.Monetary(
        string='Non-Operational Minor Max',
        currency_field='currency_id',
    )
    zvy_nop_medium_max = fields.Monetary(
        string='Non-Operational Medium Max',
        currency_field='currency_id',
    )
    zvy_nop_major_max = fields.Monetary(
        string='Non-Operational Major Max',
        currency_field='currency_id',
    )
    zvy_nop_large_ceo_max = fields.Monetary(
        string='Non-Operational Large CEO Max',
        currency_field='currency_id',
        help='Within large non-operational purchases, CEO signs up to this amount; Board above it.',
    )
    zvy_signatory_minor_ids = fields.Many2many(
        'res.users',
        'zvy_company_signatory_minor_rel',
        'company_id',
        'user_id',
        string='Minor Signatories',
        help='Commercial Manager approvers for minor (خرد) purchases.',
    )
    zvy_signatory_medium_ids = fields.Many2many(
        'res.users',
        'zvy_company_signatory_medium_rel',
        'company_id',
        'user_id',
        string='Medium Signatories',
        help='Commercial Deputy approvers for medium (متوسط) purchases.',
    )
    zvy_signatory_major_ids = fields.Many2many(
        'res.users',
        'zvy_company_signatory_major_rel',
        'company_id',
        'user_id',
        string='Major Signatories',
        help='CEO approvers for major (عمده) purchases.',
    )
    zvy_signatory_large_ids = fields.Many2many(
        'res.users',
        'zvy_company_signatory_large_rel',
        'company_id',
        'user_id',
        string='Large Signatories',
        help='CEO approvers for large (کلان) purchases up to the inner CEO ceiling.',
    )
    zvy_signatory_board_ids = fields.Many2many(
        'res.users',
        'zvy_company_signatory_board_rel',
        'company_id',
        'user_id',
        string='Board Signatories',
        help='Board member approvers for large purchases above the inner CEO ceiling.',
    )
    zvy_signatory_formalities_ids = fields.Many2many(
        'res.users',
        'zvy_company_signatory_formalities_rel',
        'company_id',
        'user_id',
        string='Formalities Signatories',
        help='Extra approvers appended when the PR is in formalities (تشریفات).',
    )

    def _zvy_band_ceilings(self, nature):
        """Return inclusive ceiling dict for this company and purchase nature."""
        self.ensure_one()
        nature = nature if nature in ('operational', 'non_operational') else 'operational'
        if self.zvy_use_custom_bands:
            prefix = 'zvy_op_' if nature == 'operational' else 'zvy_nop_'
            return {
                'minor_max': self[prefix + 'minor_max'] or 0.0,
                'medium_max': self[prefix + 'medium_max'] or 0.0,
                'major_max': self[prefix + 'major_max'] or 0.0,
                'large_ceo_max': self[prefix + 'large_ceo_max'] or 0.0,
            }
        scale = self.zvy_company_scale or 'small'
        row = ZVY_PURCHASE_BANDS.get(scale) or ZVY_PURCHASE_BANDS['small']
        values = row.get(nature) or row['operational']
        return dict(zip(ZVY_BAND_KEYS, values))

    def _zvy_purchase_level(self, amount, nature):
        self.ensure_one()
        return zvy_level_from_amount(amount, self._zvy_band_ceilings(nature))

    def _zvy_holding_company(self):
        """Head holding: top of the company tree (`root_id`), or self if standalone."""
        self.ensure_one()
        return self.root_id or self

    def _zvy_signatory_users(self, level, amount, nature):
        """Users for this purchase level. Large uses CEO or Board, not both."""
        self.ensure_one()
        if level == 'minor':
            return self.zvy_signatory_minor_ids
        if level == 'medium':
            return self.zvy_signatory_medium_ids
        if level == 'major':
            return self.zvy_signatory_major_ids
        if level == 'large':
            ceilings = self._zvy_band_ceilings(nature)
            if (amount or 0.0) <= ceilings['large_ceo_max']:
                return self.zvy_signatory_large_ids
            return self.zvy_signatory_board_ids
        return self.env['res.users']
