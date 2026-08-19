# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZvyRequestAwardNotLowestWizard(models.TransientModel):
    _name = 'zvy.request.award.not.lowest.wizard'
    _description = 'Award a Quote That Is Not the Lowest Price'

    quote_id = fields.Many2one(
        'zvy.quote',
        string='Quote',
        required=True,
        ondelete='cascade',
    )
    reason = fields.Text(
        string='Reason',
        required=True,
        help='Explain why this quote is awarded instead of a lower-priced offer.',
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise ValidationError(_(
                'A reason is required when awarding a quote that is not '
                'the lowest price.'
            ))
        reason = self.reason.strip()
        quote = self.quote_id
        quote.line_id.sudo().write({'award_not_lowest_reason': reason})
        return quote.with_env(self.env).with_context(
            zvy_ui_award=False,
            zvy_award_not_lowest_reason=reason,
        ).action_select_as_awarded()
