# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ZvyCommissionCase(models.Model):
    _name = 'zvy.commission.case'
    _description = 'Holding Commission Case'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
        tracking=True,
    )
    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='request_id.company_id',
        store=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('in_review', 'In Review'),
            ('meeting', 'Meeting'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('corrections', 'Corrections'),
        ],
        default='open',
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    reason_high_value = fields.Boolean(string='Routed: High Value')
    reason_commission_item = fields.Boolean(string='Routed: Commission Item')
    expert_user_ids = fields.Many2many(
        'res.users',
        'zvy_commission_case_expert_rel',
        'case_id',
        'user_id',
        string='Commission Experts',
        domain=lambda self: [
            ('groups_id', 'in', [
                self.env.ref('zvy_tendering.group_zvy_commission_expert').id,
            ]),
        ],
    )
    review_ids = fields.One2many(
        'zvy.commission.review',
        'case_id',
        string='Reviews',
    )
    meeting_id = fields.Many2one(
        'zvy.commission.meeting',
        string='Meeting',
        ondelete='set null',
        copy=False,
    )
    manager_decision = fields.Selection(
        selection=[
            ('approve', 'Approve'),
            ('reject', 'Reject'),
            ('corrections', 'Request Corrections'),
        ],
        string='Manager Decision',
        copy=False,
    )
    manager_notes = fields.Text(string='Manager Notes', copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) in (False, _('New'), 'New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'zvy.commission.case'
                ) or _('New')
        return super().create(vals_list)

    def action_assign_experts(self):
        self.ensure_one()
        if self.state not in ('open', 'in_review', 'meeting'):
            raise UserError(_(
                'Experts can only be assigned on open, in-review, or meeting cases.'
            ))
        if not self.expert_user_ids:
            raise ValidationError(_(
                'Select at least one Commission Expert before assigning.'
            ))
        Review = self.env['zvy.commission.review'].sudo()
        existing = {r.expert_user_id.id for r in self.review_ids}
        for expert in self.expert_user_ids:
            if expert.id not in existing:
                Review.create({
                    'case_id': self.id,
                    'expert_user_id': expert.id,
                })
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=expert.id,
                summary=_('Commission review on %s') % self.name,
                note=_(
                    'You have been assigned to review commission case %s '
                    '(PR %s).'
                ) % (self.name, self.request_id.name),
            )
        if self.state == 'open':
            self.write({'state': 'in_review'})
        self.message_post(body=_('Commission experts assigned.'))
        return True

    def _ensure_manager(self):
        if self.env.su:
            return
        is_mgr = self.env.user.has_group(
            'zvy_tendering.group_zvy_commission_manager'
        )
        is_admin = self.env.user.has_group(
            'zvy_tendering.group_zvy_tendering_admin'
        )
        if not (is_mgr or is_admin):
            raise UserError(_(
                'Only Commission Managers can perform this action.'
            ))

    def _all_reviews_approve(self):
        self.ensure_one()
        if not self.review_ids:
            return False
        return all(
            r.state == 'submitted' and r.recommendation == 'approve'
            for r in self.review_ids
        )

    def action_approve_without_meeting(self):
        self.ensure_one()
        self._ensure_manager()
        if self.state not in ('in_review', 'meeting'):
            raise UserError(_(
                'Approve without meeting is only available in review or meeting.'
            ))
        if not self._all_reviews_approve():
            raise UserError(_(
                'All assigned experts must submit an approve recommendation '
                'before approving without a meeting.'
            ))
        return self._action_manager_approve()

    def action_manager_approve(self):
        self.ensure_one()
        self._ensure_manager()
        if self.state not in ('in_review', 'meeting'):
            raise UserError(_(
                'Only in-review or meeting cases can be approved.'
            ))
        return self._action_manager_approve()

    def action_manager_reject(self):
        self.ensure_one()
        self._ensure_manager()
        if self.state not in ('open', 'in_review', 'meeting'):
            raise UserError(_(
                'Only open, in-review, or meeting cases can be rejected.'
            ))
        self.write({
            'state': 'rejected',
            'manager_decision': 'reject',
        })
        self.message_post(body=_('Commission case rejected by manager.'))
        self.request_id.sudo().message_post(body=_(
            'Holding Commission rejected case %s.'
        ) % self.name)
        return True

    def action_manager_corrections(self):
        self.ensure_one()
        self._ensure_manager()
        if self.state not in ('in_review', 'meeting'):
            raise UserError(_(
                'Corrections can only be requested from in-review or meeting.'
            ))
        self.write({
            'state': 'corrections',
            'manager_decision': 'corrections',
        })
        pr = self.request_id.sudo()
        pr.write({'state': 'quote_review'})
        pr.message_post(body=_(
            'Holding Commission requested corrections (%s); returned to quote review.'
        ) % self.name)
        self.message_post(body=_('Corrections requested; PR returned to quote review.'))
        return True

    def _action_manager_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'manager_decision': 'approve',
        })
        pr = self.request_id.sudo()
        pr.write({'state': 'signatory'})
        pr.message_post(body=_(
            'Holding Commission approved (%s); routed to company signatory path.'
        ) % self.name)
        self.message_post(body=_('Case approved; PR advanced to signatory.'))
        return True
