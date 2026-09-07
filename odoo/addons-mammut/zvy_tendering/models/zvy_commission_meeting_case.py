# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_TERMINAL_DECISIONS = ('approved', 'rejected', 'needs_correction')


class ZvyCommissionMeetingCase(models.Model):
    _name = 'zvy.commission.meeting.case'
    _description = 'Commission Meeting Agenda Item'
    _order = 'id'

    meeting_id = fields.Many2one(
        'zvy.commission.meeting',
        string='Meeting',
        required=True,
        ondelete='cascade',
        index=True,
    )
    case_id = fields.Many2one(
        'zvy.commission.case',
        string='Commission Case',
        required=True,
        ondelete='restrict',
        index=True,
        domain="[('company_id', '=', parent.requesting_company_id), "
               "('state', 'in', ('open', 'in_review', 'meeting'))]",
    )
    request_id = fields.Many2one(
        related='case_id.request_id',
        store=True,
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
    review_status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('reviewed', 'Reviewed'),
            ('removed', 'Removed'),
        ],
        default='pending',
        required=True,
        index=True,
    )
    decision = fields.Selection(
        selection=[
            ('undecided', 'Undecided'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('needs_correction', 'Needs Correction'),
        ],
        default='undecided',
        required=True,
    )
    correction_reason = fields.Text(
        string='Correction Reason',
        help='Required when the agenda decision is Needs Correction (FR-45).',
    )

    _sql_constraints = [
        (
            'meeting_case_uniq',
            'unique(meeting_id, case_id)',
            'A purchase request can appear only once on a meeting.',
        ),
    ]

    @api.constrains('case_id', 'meeting_id')
    def _check_requesting_company(self):
        for row in self:
            if not row.case_id or not row.meeting_id:
                continue
            if row.case_id.company_id != row.meeting_id.requesting_company_id:
                raise ValidationError(_(
                    'All linked purchase requests must belong to the requesting '
                    'company of this meeting.'
                ))

    @api.model_create_multi
    def create(self, vals_list):
        Meeting = self.env['zvy.commission.meeting']
        for vals in vals_list:
            meeting = Meeting.browse(vals.get('meeting_id'))
            if meeting.state in ('signed', 'cancelled'):
                raise UserError(_(
                    'Cannot add items to a signed or cancelled meeting.'
                ))
        rows = super().create(vals_list)
        rows._sync_case_on_link()
        rows._apply_terminal_decisions()
        return rows

    def write(self, vals):
        if 'decision' in vals:
            for row in self:
                if row.review_status == 'removed':
                    raise UserError(_(
                        'Cannot change the decision of a transferred item.'
                    ))
                if (
                    row.review_status == 'reviewed'
                    and vals['decision'] != row.decision
                ):
                    raise UserError(_(
                        'The decision for this item is already recorded.'
                    ))
                if row.meeting_id.state == 'cancelled':
                    raise UserError(_(
                        'Cannot record a decision on a cancelled meeting.'
                    ))
        res = super().write(vals)
        if 'decision' in vals:
            self._apply_terminal_decisions()
        return res

    @api.constrains('decision', 'correction_reason')
    def _check_correction_reason(self):
        for row in self:
            if row.decision != 'needs_correction':
                continue
            if not (row.correction_reason or '').strip():
                raise ValidationError(_(
                    'A correction reason is required when the agenda decision '
                    'is Needs Correction.'
                ))

    def _sync_case_on_link(self):
        for row in self:
            if row.review_status == 'removed':
                continue
            case = row.case_id
            case_vals = {'meeting_id': row.meeting_id.id}
            if case.state in ('open', 'in_review'):
                case_vals['state'] = 'meeting'
            case.sudo().write(case_vals)
            row.meeting_id._sync_envelope_opening(case)
            row.meeting_id.message_post(body=_(
                'Linked case %s (%s) to this meeting.'
            ) % (case.name, case.request_id.name))

    def _apply_terminal_decisions(self):
        if self.env.context.get('zvy_skip_meeting_decision'):
            return
        for row in self:
            if row.review_status == 'removed':
                continue
            if row.decision not in _TERMINAL_DECISIONS:
                continue
            if row.meeting_id.state not in ('held', 'signed'):
                raise UserError(_(
                    'Record a decision only after the meeting is held.'
                ))
            case = row.case_id
            case._ensure_manager()
            if row.decision == 'approved':
                if case.state in ('in_review', 'meeting'):
                    case._action_manager_approve()
            elif row.decision == 'rejected':
                if case.state in ('open', 'in_review', 'meeting'):
                    case.action_manager_reject()
            elif row.decision == 'needs_correction':
                if case.state in ('in_review', 'meeting'):
                    case._action_manager_corrections(row.correction_reason)
            if row.review_status != 'reviewed':
                row.with_context(zvy_skip_meeting_decision=True).write({
                    'review_status': 'reviewed',
                })

    def action_transfer(self):
        self.ensure_one()
        if not self._can_transfer():
            raise UserError(_(
                'Only pending or undecided items can be transferred.'
            ))
        return {
            'name': _('Transfer to Another Meeting'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.meeting.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_meeting_case_id': self.id},
        }

    def _can_transfer(self):
        self.ensure_one()
        return (
            self.review_status != 'removed'
            and self.decision == 'undecided'
        )

    def _action_transfer_to(self, target_meeting):
        self.ensure_one()
        if not self._can_transfer():
            raise UserError(_(
                'Only pending or undecided items can be transferred.'
            ))
        if target_meeting.state != 'scheduled':
            raise UserError(_(
                'Transfer is only allowed to a scheduled meeting.'
            ))
        if target_meeting.requesting_company_id != self.meeting_id.requesting_company_id:
            raise UserError(_(
                'The target meeting must be for the same requesting company.'
            ))
        if target_meeting == self.meeting_id:
            raise UserError(_('Choose a different meeting.'))
        source = self.meeting_id
        case = self.case_id
        self.with_context(zvy_skip_meeting_decision=True).write({
            'review_status': 'removed',
        })
        self.env['zvy.commission.meeting.case'].create({
            'meeting_id': target_meeting.id,
            'case_id': case.id,
        })
        source.message_post(body=_(
            'Transferred case %s (%s) to meeting %s.'
        ) % (case.name, case.request_id.name, target_meeting.name))
        target_meeting.message_post(body=_(
            'Received case %s (%s) from meeting %s.'
        ) % (case.name, case.request_id.name, source.name))
        return True
