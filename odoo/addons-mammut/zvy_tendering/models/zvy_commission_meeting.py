# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class ZvyCommissionMeeting(models.Model):
    _name = 'zvy.commission.meeting'
    _description = 'Commission Meeting'
    _order = 'datetime desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Title', required=True, tracking=True)
    datetime = fields.Datetime(
        string='Meeting Date',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    case_ids = fields.Many2many(
        'zvy.commission.case',
        'zvy_commission_meeting_case_rel',
        'meeting_id',
        'case_id',
        string='Cases',
    )
    mom_attachment_ids = fields.Many2many(
        'ir.attachment',
        'zvy_commission_meeting_ir_attachment_rel',
        'meeting_id',
        'attachment_id',
        string='Minutes (MOM)',
    )
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        meetings = super().create(vals_list)
        meetings._sync_case_meeting_links()
        return meetings

    def write(self, vals):
        res = super().write(vals)
        if 'case_ids' in vals:
            self._sync_case_meeting_links()
        return res

    def _sync_case_meeting_links(self):
        """Link meeting on cases and move open/in_review cases to meeting."""
        for meeting in self:
            for case in meeting.case_ids:
                vals = {'meeting_id': meeting.id}
                if case.state in ('open', 'in_review'):
                    vals['state'] = 'meeting'
                case.sudo().write(vals)
            meeting.message_post(body=_(
                'Meeting linked to %s case(s).'
            ) % len(meeting.case_ids))
