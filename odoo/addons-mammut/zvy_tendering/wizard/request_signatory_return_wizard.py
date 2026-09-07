# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZvyRequestSignatoryReturnWizard(models.TransientModel):
    _name = 'zvy.request.signatory.return.wizard'
    _description = 'Return Signatory Approval for Correction'

    approval_request_id = fields.Many2one(
        'approval.request',
        string='Approval',
        required=True,
        ondelete='cascade',
    )
    reason = fields.Text(string='Return Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('A return reason is required.'))
        self.approval_request_id.with_context(
            zvy_skip_return_wizard=True,
            zvy_refuse_reason=self.reason.strip(),
        ).action_refuse()
        return {'type': 'ir.actions.act_window_close'}
