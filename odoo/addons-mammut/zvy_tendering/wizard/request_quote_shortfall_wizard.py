# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZvyRequestQuoteShortfallWizard(models.TransientModel):
    _name = 'zvy.request.quote.shortfall.wizard'
    _description = 'Submit Fewer than 3 Quotes'

    line_ids = fields.Many2many(
        'zvy.purchase.request.line',
        'zvy_quote_shortfall_wizard_line_rel',
        'wizard_id',
        'line_id',
        string='Lines',
        required=True,
    )
    reason = fields.Text(
        string='Reason',
        required=True,
        help='Explain why fewer than 3 quotes are being submitted.',
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise ValidationError(_(
                'A reason is required when submitting fewer than 3 quotes.'
            ))
        if not self.line_ids:
            raise ValidationError(_('Select at least one purchase request line.'))
        reason = self.reason.strip()
        self.line_ids.sudo().write({'quote_shortfall_reason': reason})
        return self.line_ids.with_env(self.env).with_context(
            zvy_ui_submit=False,
        ).action_submit_quotes()
