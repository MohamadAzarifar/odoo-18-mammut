# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZvyRequestReturnWizard(models.TransientModel):
    _name = 'zvy.request.return.wizard'
    _description = 'Return Purchase Request for Correction'

    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade',
    )
    reason = fields.Text(string='Return Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('A return reason is required.'))
        self.request_id._action_return_correction(self.reason)
        return {'type': 'ir.actions.act_window_close'}
