# -*- coding: utf-8 -*-

from odoo import fields, models


class FollowupCallStatus(models.Model):
    _name = 'followup.call.status'
    _description = 'Follow-up Call Status'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
