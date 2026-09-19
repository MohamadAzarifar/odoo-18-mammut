# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..hooks import ensure_res_company_columns

from .zvy_purchase_bands import (
    ZVY_BAND_KEYS,
    ZVY_PURCHASE_BANDS,
    zvy_level_from_amount,
)


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def _prepare_setup(self):
        # Columns must exist before setup_models reinstalls hooks and flushes
        # env.company (UI install/upgrade on a ready registry, and restart
        # without -u after deploying new fields).
        ensure_res_company_columns(self.env.cr)
        super()._prepare_setup()

    zvy_default_bid_window_hours = fields.Integer(
        string='Default Bid Window (Hours)',
        default=72,
        help='Default hours from list approval to bid deadline for closed-envelope tenders.',
    )
    zvy_signatory_approval_category_id = fields.Many2one(
        'approval.category',
        string='Signatory Approval Category',
        help='Sequential approval category used as the signatory document '
             'template. Approver users come from the per-band HR jobs, not '
             'from this category.',
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
    zvy_signatory_minor_job_id = fields.Many2one(
        'hr.job',
        string='Minor Signatory Job',
        check_company=True,
        help='Job whose employees all approve minor (خرد) purchases '
             '(e.g. Commercial Manager).',
    )
    zvy_signatory_medium_job_id = fields.Many2one(
        'hr.job',
        string='Medium Signatory Job',
        check_company=True,
        help='Job whose employees all approve medium (متوسط) purchases '
             '(e.g. Commercial Deputy).',
    )
    zvy_signatory_major_job_id = fields.Many2one(
        'hr.job',
        string='Major Signatory Job',
        check_company=True,
        help='Job whose employees all approve major (عمده) purchases (e.g. CEO).',
    )
    zvy_signatory_large_job_id = fields.Many2one(
        'hr.job',
        string='Large Signatory Job',
        check_company=True,
        help='Job whose employees all approve large (کلان) purchases up to '
             'the inner CEO ceiling.',
    )
    zvy_signatory_board_job_id = fields.Many2one(
        'hr.job',
        string='Board Signatory Job',
        check_company=True,
        help='Job whose employees all approve large purchases above the '
             'inner CEO ceiling.',
    )
    zvy_signatory_formalities_job_id = fields.Many2one(
        'hr.job',
        string='Formalities Signatory Job',
        check_company=True,
        help='Extra job whose employees are appended when the PR is in '
             'formalities (تشریفات).',
    )
    zvy_commission_notice_days = fields.Integer(
        string='Commission Notice Days',
        default=0,
        help='Minimum days between PR date and commission review/meeting date '
             '(US-06 check 1). 0 disables the window until the commission-laws '
             'document is available.',
    )
    zvy_commission_require_proforma = fields.Boolean(
        string='Require Awarded Proforma',
        help='Commission pre-check 5 fails when an awarded inquiry has no proforma.',
    )
    zvy_commission_require_comparison = fields.Boolean(
        string='Require Comparison Document',
        help='Commission pre-check 5 fails when the PR has no comparison attachment.',
    )
    zvy_commission_require_technical = fields.Boolean(
        string='Require Technical Request',
        help='Commission pre-check 5 fails when the PR has no technical-request attachment.',
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

    def _zvy_signatory_job(self, level, amount, nature):
        """HR job for this purchase level. Large uses CEO or Board, not both."""
        self.ensure_one()
        # Spawn runs as CM/admin; hr.job is Officer-restricted.
        company = self.sudo()
        if level == 'minor':
            return company.zvy_signatory_minor_job_id
        if level == 'medium':
            return company.zvy_signatory_medium_job_id
        if level == 'major':
            return company.zvy_signatory_major_job_id
        if level == 'large':
            ceilings = self._zvy_band_ceilings(nature)
            if (amount or 0.0) <= ceilings['large_ceo_max']:
                return company.zvy_signatory_large_job_id
            return company.zvy_signatory_board_job_id
        return self.env['hr.job']

    def _zvy_users_from_job(self, job, *, require_users=True):
        """Active employees on ``job`` for this company, as linked users.

        Order is stable by employee id. Every member must have a Related User
        when ``require_users`` is True (spawn / inject paths).
        """
        self.ensure_one()
        job = job.sudo() if job else job
        if not job:
            return self.env['res.users']
        employees = self.env['hr.employee'].sudo().search([
            ('job_id', '=', job.id),
            ('company_id', '=', self.id),
            ('active', '=', True),
        ], order='id')
        missing = employees.filtered(lambda e: not e.user_id)
        if missing and require_users:
            raise UserError(_(
                'Employees on job "%(job)s" must have a Related User before '
                'they can sign: %(names)s.',
                job=job.display_name,
                names=', '.join(missing.mapped('name')),
            ))
        user_ids = []
        seen = set()
        for employee in employees.filtered('user_id'):
            uid = employee.user_id.id
            if uid in seen:
                continue
            seen.add(uid)
            user_ids.append(uid)
        users = self.env['res.users'].browse(user_ids)
        if require_users and job and not users:
            raise UserError(_(
                'Job "%(job)s" has no active employees with a Related User '
                'in company "%(company)s".',
                job=job.display_name,
                company=self.display_name,
            ))
        return users

    def _zvy_signatory_users(self, level, amount, nature):
        """Users for this purchase level, resolved from the configured HR job."""
        self.ensure_one()
        job = self._zvy_signatory_job(level, amount, nature)
        if not job:
            return self.env['res.users']
        return self._zvy_users_from_job(job)
