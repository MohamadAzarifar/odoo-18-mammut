# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZvyCommissionCorrectionsWizard(models.TransientModel):
    _name = 'zvy.commission.corrections.wizard'
    _description = 'Request Commission Corrections'

    case_id = fields.Many2one(
        'zvy.commission.case',
        string='Commission Case',
        required=True,
        ondelete='cascade',
    )
    reason = fields.Text(string='Correction Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('A return reason is required.'))
        self.case_id._action_manager_corrections(self.reason)
        return {'type': 'ir.actions.act_window_close'}
