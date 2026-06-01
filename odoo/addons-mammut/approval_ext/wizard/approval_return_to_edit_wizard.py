# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ApprovalReturnToEditWizard(models.TransientModel):
    _name = 'approval.return.to.edit.wizard'
    _description = 'Return approval request for editing'

    request_id = fields.Many2one(
        'approval.request',
        string='Request',
        required=True,
        ondelete='cascade',
    )
    reason = fields.Text(
        string='Reason',
        required=True,
        help='Explain what must be changed. The requester will see this in the chatter.',
    )

    def action_apply(self):
        self.ensure_one()
        self.request_id.approval_ext_apply_return_to_editing(self.reason)
        return {'type': 'ir.actions.act_window_close'}
