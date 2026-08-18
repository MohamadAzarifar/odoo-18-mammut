# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class ZvyRequestSplitWizard(models.TransientModel):
    _name = 'zvy.request.split.wizard'
    _description = 'Split Mixed Purchase Request'

    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade',
    )
    note = fields.Text(
        string='Message',
        default=lambda self: _(
            'This purchase request contains both Enquiry and Tendering products. '
            'They must be submitted as two separate purchase requests.\n\n'
            'Split now? Enquiry lines stay on this request; Tendering lines '
            'move to a new draft request. Neither request is submitted.'
        ),
        readonly=True,
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.request_id:
            raise UserError(_('A purchase request is required.'))
        self.request_id.action_split_mixed()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'zvy.purchase.request',
            'res_id': self.request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
