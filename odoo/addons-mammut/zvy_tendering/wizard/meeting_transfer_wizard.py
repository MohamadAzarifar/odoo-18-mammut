# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class ZvyMeetingTransferWizard(models.TransientModel):
    _name = 'zvy.meeting.transfer.wizard'
    _description = 'Transfer Agenda Item to Another Meeting'

    meeting_case_id = fields.Many2one(
        'zvy.commission.meeting.case',
        string='Agenda Item',
        required=True,
        ondelete='cascade',
    )
    source_meeting_id = fields.Many2one(
        related='meeting_case_id.meeting_id',
    )
    requesting_company_id = fields.Many2one(
        related='meeting_case_id.meeting_id.requesting_company_id',
    )
    target_meeting_id = fields.Many2one(
        'zvy.commission.meeting',
        string='Target Meeting',
        required=True,
        domain="[('state', '=', 'scheduled'), "
               "('requesting_company_id', '=', requesting_company_id), "
               "('id', '!=', source_meeting_id)]",
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.target_meeting_id:
            raise ValidationError(_('Select a target meeting.'))
        if not self.meeting_case_id._can_transfer():
            raise UserError(_(
                'Only pending or undecided items can be transferred.'
            ))
        self.meeting_case_id._action_transfer_to(self.target_meeting_id)
        return {'type': 'ir.actions.act_window_close'}
