# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ZvyCeClarificationWizard(models.TransientModel):
    _name = 'zvy.ce.clarification.wizard'
    _description = 'Post Closed Envelope Clarification'

    envelope_id = fields.Many2one(
        'zvy.closed.envelope',
        string='Closed Envelope',
        required=True,
        ondelete='cascade',
    )
    body = fields.Text(string='Clarification', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.body or not self.body.strip():
            raise ValidationError(_('Clarification body is required.'))
        self.envelope_id._post_clarification(self.body)
        return {'type': 'ir.actions.act_window_close'}
