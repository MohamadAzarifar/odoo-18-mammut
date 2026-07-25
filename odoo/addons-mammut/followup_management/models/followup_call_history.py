# -*- coding: utf-8 -*-

from odoo import fields, models


class FollowupCallHistory(models.Model):
    _name = 'followup.call.history'
    _description = 'Follow-up Call History'
    _order = 'call_datetime desc, id desc'

    followup_id = fields.Many2one(
        'followup.record',
        string='Follow Up',
        required=True,
        ondelete='cascade',
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True,
    )
    call_datetime = fields.Datetime(
        string='Call DateTime',
        default=fields.Datetime.now,
        required=True,
    )
    call_status_id = fields.Many2one('followup.call.status', string='Call Status')
    comment = fields.Text()
