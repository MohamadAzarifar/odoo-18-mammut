# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZvyRequestRejectWizard(models.TransientModel):
    _name = 'zvy.request.reject.wizard'
    _description = 'Reject Purchase Request'

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
            raise ValidationError(_('A reject reason is required.'))
        self.request_id._action_reject(self.reason)
        return {'type': 'ir.actions.act_window_close'}
