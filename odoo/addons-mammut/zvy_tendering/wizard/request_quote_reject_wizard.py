# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZvyRequestQuoteRejectWizard(models.TransientModel):
    _name = 'zvy.request.quote.reject.wizard'
    _description = 'Reject Quotes'

    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade',
    )
    reason = fields.Text(string='Reject Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('A quote reject reason is required.'))
        self.request_id._action_reject_quotes(self.reason)
        return {'type': 'ir.actions.act_window_close'}
