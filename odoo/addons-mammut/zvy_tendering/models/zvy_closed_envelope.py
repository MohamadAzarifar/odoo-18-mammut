# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ZvyClosedEnvelope(models.Model):
    _name = 'zvy.closed.envelope'
    _description = 'Closed Envelope Tender'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        default=lambda self: _('New'),
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
        related='request_id.company_id',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related='request_id.currency_id',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('list_pending', 'List Pending'),
            ('portal_open', 'Portal Open'),
            ('opened', 'Opened'),
            ('awarded', 'Awarded'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft',
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    invite_partner_ids = fields.Many2many(
        'res.partner',
        'zvy_closed_envelope_invite_rel',
        'envelope_id',
        'partner_id',
        string='Invited Suppliers',
    )
    opening_datetime = fields.Datetime(string='Opening Datetime', copy=False)
    bid_deadline = fields.Datetime(string='Bid Deadline', copy=False)
    bid_ids = fields.One2many(
        'zvy.closed.envelope.bid',
        'envelope_id',
        string='Bids',
    )
    winner_partner_id = fields.Many2one(
        'res.partner',
        string='Winner',
        copy=False,
        tracking=True,
    )
    list_reject_reason = fields.Text(string='List Reject Reason', copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            request = self.env['zvy.purchase.request'].browse(
                vals.get('request_id')
            )
            if request and request.state != 'inquiry' and not self.env.su:
                raise UserError(_(
                    'Closed envelopes can only be created while the PR is in Inquiry.'
                ))
            if vals.get('name', _('New')) in (False, _('New'), 'New') and request:
                vals['name'] = _('CE/%s') % (request.name or _('New'))
        envelopes = super().create(vals_list)
        for envelope in envelopes:
            if envelope.request_id and not envelope.request_id.closed_envelope_id:
                envelope.request_id.sudo().write({
                    'closed_envelope_id': envelope.id,
                })
        return envelopes

    def _invite_partner_domain(self):
        self.ensure_one()
        return self.env['zvy.avl.entry']._avl_partner_domain(self.company_id)

    @api.constrains('invite_partner_ids', 'company_id')
    def _check_invite_avl(self):
        Avl = self.env['zvy.avl.entry']
        for envelope in self:
            if not envelope.invite_partner_ids:
                continue
            allowed = set(
                self.env['res.partner'].search(
                    Avl._avl_partner_domain(envelope.company_id)
                ).ids
            )
            bad = envelope.invite_partner_ids.filtered(
                lambda p: p.id not in allowed
            )
            if bad:
                raise ValidationError(_(
                    'Only AVL vendors may be invited: %s'
                ) % ', '.join(bad.mapped('display_name')))

    def action_submit_list(self):
        for envelope in self:
            if envelope.state != 'draft':
                raise UserError(_('Only draft lists can be submitted.'))
            if not envelope.invite_partner_ids:
                raise ValidationError(_(
                    'Add at least one invited AVL supplier before submitting.'
                ))
            if not self.env.su:
                pr = envelope.request_id
                is_cce = self.env.user.has_group(
                    'zvy_tendering.group_zvy_commercial_expert'
                )
                is_cm = self.env.user.has_group(
                    'zvy_tendering.group_zvy_commercial_manager'
                )
                is_admin = self.env.user.has_group(
                    'zvy_tendering.group_zvy_tendering_admin'
                )
                if not (is_admin or is_cm or (
                    is_cce and pr._user_is_assigned_expert()
                )):
                    raise UserError(_(
                        'Only assigned Commercial Experts can submit the invite list.'
                    ))
            if envelope.request_id.state != 'inquiry':
                raise UserError(_(
                    'The purchase request must be in Inquiry to submit a CE list.'
                ))
            envelope.write({'state': 'list_pending'})
            envelope.message_post(body=_(
                'Supplier invite list submitted for Commission Manager approval.'
            ))
        return True

    def action_approve_list(self):
        self.ensure_one()
        self._ensure_commission_manager()
        if self.state != 'list_pending':
            raise UserError(_('Only pending lists can be approved.'))
        opening = self.opening_datetime
        deadline = self.bid_deadline
        if not opening:
            raise ValidationError(_(
                'Opening datetime is required to approve the supplier list.'
            ))
        vals = {'state': 'portal_open'}
        if not deadline:
            hours = self.company_id.zvy_default_bid_window_hours or 72
            deadline = fields.Datetime.to_datetime(opening) + timedelta(hours=hours)
            vals['bid_deadline'] = deadline
        self.write(vals)
        self.message_post(body=_(
            'Invite list approved; bidding open until %s (opening %s). '
            'Portal notifications deferred to Phase 5.'
        ) % (self.bid_deadline, self.opening_datetime))
        return True

    def action_reject_list(self):
        self.ensure_one()
        self._ensure_commission_manager()
        if self.state != 'list_pending':
            raise UserError(_('Only pending lists can be rejected.'))
        reason = (self.list_reject_reason or '').strip()
        if not reason:
            raise ValidationError(_(
                'Provide a list reject reason before rejecting.'
            ))
        self.write({
            'state': 'draft',
            'list_reject_reason': reason,
        })
        self.message_post(body=_('Invite list rejected: %s') % reason)
        return True

    def action_open_bids(self):
        self.ensure_one()
        self._ensure_commission_manager()
        if self.state != 'portal_open':
            raise UserError(_('Bids can only be opened from Portal Open.'))
        if not self.opening_datetime:
            raise ValidationError(_('Opening datetime is missing.'))
        now = fields.Datetime.now()
        if now < self.opening_datetime:
            raise UserError(_(
                'Cannot open bids before the scheduled opening datetime.'
            ))
        self.write({'state': 'opened'})
        self.message_post(body=_('Bids unsealed / opened.'))
        return True

    def action_select_winner(self):
        self.ensure_one()
        self._ensure_commission_manager()
        if self.state != 'opened':
            raise UserError(_(
                'Winner can only be selected after bids are opened.'
            ))
        if not self.winner_partner_id:
            raise ValidationError(_(
                'Set the winner partner before selecting the winner.'
            ))
        if self.winner_partner_id not in self.invite_partner_ids:
            raise ValidationError(_(
                'Winner must be one of the invited suppliers.'
            ))
        self.write({'state': 'awarded'})
        pr = self.request_id.sudo()
        pr.write({
            'award_partner_id': self.winner_partner_id.id,
            'state': 'quote_review',
        })
        self.message_post(body=_(
            'Winner selected: %s. PR moved to quote review.'
        ) % self.winner_partner_id.display_name)
        pr.message_post(body=_(
            'Closed envelope awarded to %s.'
        ) % self.winner_partner_id.display_name)
        return True

    def action_cancel(self):
        for envelope in self:
            if envelope.state in ('awarded', 'cancelled'):
                raise UserError(_(
                    'Awarded or cancelled envelopes cannot be cancelled again.'
                ))
            envelope.write({'state': 'cancelled'})
            envelope.message_post(body=_('Closed envelope cancelled.'))
        return True

    def _ensure_commission_manager(self):
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
