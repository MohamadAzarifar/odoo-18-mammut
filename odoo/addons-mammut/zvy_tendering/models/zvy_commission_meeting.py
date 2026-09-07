# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
    location = fields.Char(string='Location', tracking=True)
    state = fields.Selection(
        selection=[
            ('scheduled', 'Scheduled'),
            ('held', 'Held'),
            ('signed', 'Signed'),
            ('cancelled', 'Cancelled'),
        ],
        default='scheduled',
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    requesting_company_id = fields.Many2one(
        'res.company',
        string='Requesting Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
        help='All agenda PRs must belong to this operating company.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Holding Company',
        required=True,
        index=True,
        default=lambda self: self.env.company._zvy_holding_company(),
        help='Head holding that owns the meeting (FR-42 / FR-46).',
    )
    holding_company_id = fields.Many2one(
        related='company_id.root_id',
        store=True,
        index=True,
        string='Head Holding',
    )
    minutes_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Minutes',
        ondelete='set null',
        copy=False,
        tracking=True,
    )
    notes = fields.Text(string='Notes')
    meeting_case_ids = fields.One2many(
        'zvy.commission.meeting.case',
        'meeting_id',
        string='Agenda',
    )
    attendee_ids = fields.One2many(
        'zvy.commission.meeting.attendee',
        'meeting_id',
        string='Attendees',
    )
    case_ids = fields.Many2many(
        'zvy.commission.case',
        compute='_compute_case_ids',
        string='Cases',
    )

    @api.depends(
        'meeting_case_ids.case_id',
        'meeting_case_ids.review_status',
    )
    def _compute_case_ids(self):
        for meeting in self:
            meeting.case_ids = meeting.meeting_case_ids.filtered(
                lambda row: row.review_status != 'removed'
            ).mapped('case_id')

    @api.model
    def _holding_id_for_requesting(self, requesting_id):
        requesting = self.env['res.company'].browse(requesting_id)
        if not requesting:
            requesting = self.env.company
        return requesting._zvy_holding_company().id

    @api.onchange('requesting_company_id')
    def _onchange_requesting_company_id(self):
        if self.requesting_company_id:
            self.company_id = self.requesting_company_id._zvy_holding_company()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            requesting_id = vals.get('requesting_company_id') or self.env.company.id
            vals['requesting_company_id'] = requesting_id
            vals['company_id'] = self._holding_id_for_requesting(requesting_id)
        return super().create(vals_list)

    def write(self, vals):
        if 'requesting_company_id' in vals:
            vals['company_id'] = self._holding_id_for_requesting(
                vals['requesting_company_id']
            )
        res = super().write(vals)
        if 'datetime' in vals:
            self._sync_envelope_opening()
        return res

    @api.constrains('requesting_company_id', 'meeting_case_ids')
    def _check_agenda_same_company(self):
        for meeting in self:
            bad = meeting.meeting_case_ids.filtered(
                lambda row: (
                    row.case_id.company_id
                    and row.case_id.company_id != meeting.requesting_company_id
                )
            )
            if bad:
                raise ValidationError(_(
                    'All linked purchase requests must belong to the requesting '
                    'company of this meeting.'
                ))

    def _sync_envelope_opening(self, cases=None):
        """Align CE opening datetime with the sitting when the envelope is open."""
        Envelope = self.env['zvy.closed.envelope'].sudo()
        for meeting in self:
            if not meeting.datetime:
                continue
            if cases is None:
                case_set = meeting.meeting_case_ids.filtered(
                    lambda row: row.review_status != 'removed'
                ).mapped('case_id')
            else:
                case_set = cases
            request_ids = case_set.mapped('request_id').ids
            if not request_ids:
                continue
            envelopes = Envelope.search([
                ('request_id', 'in', request_ids),
                ('state', '=', 'portal_open'),
            ])
            if envelopes:
                envelopes.write({'opening_datetime': meeting.datetime})

    def action_mark_held(self):
        self.ensure_one()
        if self.state != 'scheduled':
            raise UserError(_('Only a scheduled meeting can be marked as held.'))
        if not self.minutes_attachment_id:
            raise UserError(_(
                'Upload minutes before marking the meeting as held.'
            ))
        self.write({'state': 'held'})
        self.message_post(body=_('Meeting marked as held.'))
        return True

    def action_mark_signed(self):
        self.ensure_one()
        if self.state != 'held':
            raise UserError(_('Only a held meeting can be marked as signed.'))
        self.write({'state': 'signed'})
        self.message_post(body=_('Meeting marked as signed.'))
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state not in ('scheduled', 'held'):
            raise UserError(_(
                'Only scheduled or held meetings can be cancelled.'
            ))
        pending = self.meeting_case_ids.filtered(
            lambda row: (
                row.review_status != 'removed'
                and row.decision == 'undecided'
            )
        )
        for row in pending:
            if row.case_id.meeting_id == self:
                row.case_id.sudo().write({'meeting_id': False})
        self.write({'state': 'cancelled'})
        self.message_post(body=_(
            'Meeting cancelled. Agenda history was kept.'
        ))
        return True
