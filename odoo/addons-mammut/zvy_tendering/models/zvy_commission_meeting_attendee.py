# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ZvyCommissionMeetingAttendee(models.Model):
    _name = 'zvy.commission.meeting.attendee'
    _description = 'Commission Meeting Attendee'
    _order = 'id'

    meeting_id = fields.Many2one(
        'zvy.commission.meeting',
        string='Meeting',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='meeting_id.company_id',
        store=True,
        index=True,
        string='Company',
    )
    holding_company_id = fields.Many2one(
        related='meeting_id.holding_company_id',
        store=True,
        index=True,
        string='Head Holding',
    )
    kind = fields.Selection(
        selection=[
            ('internal', 'Internal'),
            ('external', 'External'),
        ],
        default='internal',
        required=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        ondelete='restrict',
    )
    name = fields.Char(
        compute='_compute_name',
        store=True,
        readonly=False,
    )
    role = fields.Char(string='Role')

    @api.depends('kind', 'user_id')
    def _compute_name(self):
        for row in self:
            if row.kind == 'internal' and row.user_id:
                row.name = row.user_id.name
            else:
                row.name = row.name

    @api.constrains('kind', 'user_id', 'name', 'role')
    def _check_attendee(self):
        for row in self:
            if row.kind == 'internal' and not row.user_id:
                raise ValidationError(_(
                    'Internal attendees need a user.'
                ))
            if row.kind == 'external':
                if row.user_id:
                    raise ValidationError(_(
                        'External attendees cannot have a user account.'
                    ))
                if not (row.name or '').strip() or not (row.role or '').strip():
                    raise ValidationError(_(
                        'External attendees need a name and role.'
                    ))
