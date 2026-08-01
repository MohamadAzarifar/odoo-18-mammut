# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_INTAKE_EDITABLE_STATES = ('draft', 'correction')
_CM_INTAKE_STATES = ('submitted', 'cm_review')
_ALLOWED_TRANSITIONS = {
    'draft': {'submitted'},
    'correction': {'submitted'},
    'submitted': {'rejected', 'correction', 'inquiry'},
    'cm_review': {'rejected', 'correction', 'inquiry'},
    'inquiry': {'quote_review'},
    'quote_review': {'inquiry', 'commission', 'signatory'},
    'commission': {'signatory', 'quote_review'},
}


class ZvyPurchaseRequest(models.Model):
    _name = 'zvy.purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    requester_id = fields.Many2one(
        'res.users',
        string='Requester',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )
    description = fields.Text(tracking=True)
    line_ids = fields.One2many(
        'zvy.purchase.request.line',
        'request_id',
        string='Lines',
        copy=True,
    )
    quote_ids = fields.One2many(
        'zvy.quote',
        'request_id',
        string='Quotes',
    )
    commission_case_id = fields.Many2one(
        'zvy.commission.case',
        string='Commission Case',
        copy=False,
        readonly=True,
    )
    closed_envelope_id = fields.Many2one(
        'zvy.closed.envelope',
        string='Closed Envelope',
        copy=False,
        readonly=True,
    )
    award_partner_id = fields.Many2one(
        'res.partner',
        string='Awarded Vendor',
        copy=False,
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('cm_review', 'CM Review'),
            ('inquiry', 'Inquiry'),
            ('quote_review', 'Quote Review'),
            ('commission', 'Commission'),
            ('signatory', 'Signatory'),
            ('po_ready', 'PO Ready'),
            ('done', 'Done'),
            ('correction', 'Correction'),
            ('rejected', 'Rejected'),
        ],
        default='draft',
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )
    amount_total = fields.Monetary(
        string='Total Estimate',
        currency_field='currency_id',
        compute='_compute_amount_total',
        store=True,
    )
    is_high_value = fields.Boolean(
        string='High Value',
        compute='_compute_routing_flags',
        store=True,
    )
    is_commission_item = fields.Boolean(
        string='Commission Item',
        compute='_compute_routing_flags',
        store=True,
    )
    has_sole_source = fields.Boolean(
        string='Has Sole Source',
        compute='_compute_routing_flags',
        store=True,
    )
    can_edit_quotes = fields.Boolean(
        string='Can Edit Quotes Here',
        compute='_compute_can_edit_quotes',
        depends_context=('uid',),
        help='Experts collect quotes from their assigned lines; only CM/Admin may '
             'edit the quote set on the request itself (they alone can write the PR).',
    )
    reject_reason = fields.Text(copy=False)
    return_reason = fields.Text(copy=False)
    quote_reject_reason = fields.Text(copy=False)

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for request in self:
            request.amount_total = sum(request.line_ids.mapped('price_subtotal'))

    @api.depends(
        'amount_total',
        'company_id.zvy_high_value_threshold',
        'line_ids.is_commission_item',
        'line_ids.sole_source',
    )
    def _compute_routing_flags(self):
        for request in self:
            threshold = request.company_id.zvy_high_value_threshold or 0.0
            request.is_high_value = bool(threshold and request.amount_total >= threshold)
            request.is_commission_item = any(request.line_ids.mapped('is_commission_item'))
            request.has_sole_source = any(request.line_ids.mapped('sole_source'))

    @api.depends('state')
    def _compute_can_edit_quotes(self):
        is_cm = self.env.user.has_group('zvy_tendering.group_zvy_commercial_manager')
        is_admin = self.env.user.has_group('zvy_tendering.group_zvy_tendering_admin')
        for request in self:
            request.can_edit_quotes = (
                request.state == 'inquiry' and (is_cm or is_admin)
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) in (False, _('New'), 'New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'zvy.purchase.request'
                ) or _('New')
            if vals.get('company_id') and not vals.get('currency_id'):
                company = self.env['res.company'].browse(vals['company_id'])
                vals['currency_id'] = company.currency_id.id
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals:
            new_state = vals['state']
            for request in self:
                if new_state != request.state:
                    allowed = _ALLOWED_TRANSITIONS.get(request.state, set())
                    if new_state not in allowed:
                        raise UserError(_(
                            'Transition from %(current)s to %(target)s is not allowed.',
                            current=request.state,
                            target=new_state,
                        ))
        content_keys = set(vals) - {
            'state',
            'reject_reason',
            'return_reason',
            'quote_reject_reason',
            'commission_case_id',
            'closed_envelope_id',
            'award_partner_id',
            'message_main_attachment_id',
            'quote_ids',
        }
        if content_keys and not self.env.su:
            locked = self.filtered(lambda r: r.state not in _INTAKE_EDITABLE_STATES)
            if locked:
                raise UserError(_(
                    'Purchase request %(name)s can only be edited in Draft or Correction.',
                    name=locked[0].name,
                ))
        return super().write(vals)

    def unlink(self):
        for request in self:
            if request.state != 'draft':
                raise UserError(_(
                    'Only draft purchase requests can be deleted.'
                ))
        return super().unlink()

    def action_submit(self):
        for request in self:
            if request.state not in _INTAKE_EDITABLE_STATES:
                raise UserError(_(
                    'Only draft or correction requests can be submitted.'
                ))
            if not request.line_ids:
                raise ValidationError(_(
                    'Add at least one line before submitting the purchase request.'
                ))
            request.write({'state': 'submitted'})
            request.message_post(body=_('Purchase request submitted for CM review.'))
        return True

    def action_reject(self):
        self.ensure_one()
        if self.state not in _CM_INTAKE_STATES:
            raise UserError(_(
                'Only submitted or CM-review requests can be rejected.'
            ))
        return {
            'name': _('Reject Purchase Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_return_correction(self):
        self.ensure_one()
        if self.state not in _CM_INTAKE_STATES:
            raise UserError(_(
                'Only submitted or CM-review requests can be returned for correction.'
            ))
        return {
            'name': _('Return for Correction'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_assign_experts(self):
        self.ensure_one()
        if self.state not in _CM_INTAKE_STATES and self.state != 'inquiry':
            raise UserError(_(
                'Experts can only be assigned from submitted, CM review, or inquiry.'
            ))
        return {
            'name': _('Assign Commercial Experts'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_submit_quotes(self):
        """Submit every line assigned to the caller (FR-10).

        Experts normally submit per line from My Assignments; this keeps the
        request-level entry point working for multi-line assignments.
        """
        self.ensure_one()
        if self.state != 'inquiry':
            raise UserError(_('Quotes can only be submitted from Inquiry.'))
        if self._ce_award_satisfies_inquiry():
            self._try_advance_to_quote_review()
            return True
        lines = self.sudo().line_ids
        if not self.env.su:
            is_admin = self.env.user.has_group('zvy_tendering.group_zvy_tendering_admin')
            if not is_admin:
                lines = lines.filtered(
                    lambda l: self.env.user in l.expert_user_ids
                )
                if not lines:
                    raise UserError(_(
                        'Only assigned Commercial Experts can submit quotes.'
                    ))
            lines = lines.filtered(lambda l: not l.quotes_submitted)
            if not lines:
                raise UserError(_(
                    'Your quote sets on this request were already submitted.'
                ))
        return lines.with_env(self.env).action_submit_quotes()

    def _try_advance_to_quote_review(self):
        """Move to quote review once every line has submitted its quote set."""
        for request in self.sudo():
            if request.state != 'inquiry':
                continue
            if not request._ce_award_satisfies_inquiry():
                if not request.line_ids:
                    continue
                if not all(request.line_ids.mapped('quotes_submitted')):
                    continue
            request.write({'state': 'quote_review'})
            request.message_post(body=_(
                'All quote sets submitted; request ready for CM review.'
            ))
        return True

    def action_create_closed_envelope(self):
        self.ensure_one()
        if self.state != 'inquiry':
            raise UserError(_(
                'Closed envelopes can only be created while the PR is in Inquiry.'
            ))
        if self.closed_envelope_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Closed Envelope'),
                'res_model': 'zvy.closed.envelope',
                'res_id': self.closed_envelope_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        if not self._user_is_assigned_expert() and not self.env.su:
            is_cm = self.env.user.has_group('zvy_tendering.group_zvy_commercial_manager')
            is_admin = self.env.user.has_group('zvy_tendering.group_zvy_tendering_admin')
            if not (is_cm or is_admin):
                raise UserError(_(
                    'Only assigned Commercial Experts can create a closed envelope.'
                ))
        envelope = self.env['zvy.closed.envelope'].sudo().create({
            'request_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Closed Envelope'),
            'res_model': 'zvy.closed.envelope',
            'res_id': envelope.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _ce_award_satisfies_inquiry(self):
        self.ensure_one()
        return bool(
            self.closed_envelope_id
            and self.closed_envelope_id.state == 'awarded'
        )

    def action_approve_quotes(self):
        self.ensure_one()
        if self.state != 'quote_review':
            raise UserError(_('Only quote-review requests can have quotes approved.'))
        self.quote_ids.filtered(lambda q: q.state == 'submitted').sudo().write({
            'state': 'accepted',
        })
        self.message_post(body=_('Quotes approved; routing purchase request.'))
        return self._action_route_after_quotes()

    def action_reject_quotes(self):
        self.ensure_one()
        if self.state != 'quote_review':
            raise UserError(_('Only quote-review requests can have quotes rejected.'))
        return {
            'name': _('Reject Quotes'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.quote.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def _action_reject(self, reason):
        self.ensure_one()
        if not reason or not reason.strip():
            raise ValidationError(_('A reject reason is required.'))
        if self.state not in _CM_INTAKE_STATES:
            raise UserError(_(
                'Only submitted or CM-review requests can be rejected.'
            ))
        self.write({
            'state': 'rejected',
            'reject_reason': reason.strip(),
        })
        self.message_post(body=_('Rejected: %s') % reason.strip())
        self._notify_planner('reject', reason.strip())

    def _action_return_correction(self, reason):
        self.ensure_one()
        if not reason or not reason.strip():
            raise ValidationError(_('A return reason is required.'))
        if self.state not in _CM_INTAKE_STATES:
            raise UserError(_(
                'Only submitted or CM-review requests can be returned for correction.'
            ))
        self.write({
            'state': 'correction',
            'return_reason': reason.strip(),
        })
        self.message_post(body=_('Returned for correction: %s') % reason.strip())
        self._notify_planner('return', reason.strip())

    def _action_assign_experts(self, line_assignments):
        """Assign experts and move to inquiry.

        :param line_assignments: dict {line_id: [user_id, ...]}
        """
        self.ensure_one()
        if self.state not in _CM_INTAKE_STATES and self.state != 'inquiry':
            raise UserError(_(
                'Experts can only be assigned from submitted, CM review, or inquiry.'
            ))
        if not self.line_ids:
            raise ValidationError(_('Cannot assign experts on a request with no lines.'))
        for line in self.line_ids:
            expert_ids = line_assignments.get(line.id, [])
            if not expert_ids:
                raise ValidationError(_(
                    'Assign at least one Commercial Expert to every line.'
                ))
            line.write({'expert_user_ids': [(6, 0, expert_ids)]})
        if self.state != 'inquiry':
            self.write({'state': 'inquiry'})
        experts = self.line_ids.mapped('expert_user_ids')
        self.message_post(body=_('Commercial experts assigned; inquiry started.'))
        for expert in experts:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=expert.id,
                summary=_('Inquiry assignment on %s') % self.name,
                note=_(
                    'You have been assigned to collect quotes for purchase request %s.'
                ) % self.name,
            )
        return True

    def _action_reject_quotes(self, reason):
        self.ensure_one()
        if not reason or not reason.strip():
            raise ValidationError(_('A quote reject reason is required.'))
        if self.state != 'quote_review':
            raise UserError(_('Only quote-review requests can have quotes rejected.'))
        reason = reason.strip()
        self.quote_ids.filtered(
            lambda q: q.state in ('submitted', 'accepted')
        ).sudo().write({'state': 'draft'})
        self.write({
            'state': 'inquiry',
            'quote_reject_reason': reason,
        })
        self.message_post(body=_('Quotes rejected: %s') % reason)
        experts = self.line_ids.mapped('expert_user_ids')
        for expert in experts:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=expert.id,
                summary=_('Quotes rejected on %s') % self.name,
                note=_(
                    'Quotes on purchase request %s were rejected.\nReason: %s'
                ) % (self.name, reason),
            )
        return True

    def _check_quote_minima(self):
        self.ensure_one()
        self.sudo().line_ids._check_quote_minima()

    def _user_is_assigned_expert(self):
        self.ensure_one()
        # Experts only read their own lines; assignment spans the whole PR.
        return self.env.user in self.sudo().line_ids.expert_user_ids

    def _action_route_after_quotes(self):
        self.ensure_one()
        if self.is_commission_item or self.is_high_value:
            case = self.env['zvy.commission.case'].sudo().create({
                'request_id': self.id,
                'reason_high_value': self.is_high_value,
                'reason_commission_item': self.is_commission_item,
            })
            self.write({
                'commission_case_id': case.id,
                'state': 'commission',
            })
            self.message_post(body=_(
                'Routed to Holding Commission (%s).'
            ) % case.name)
        else:
            # Phase 4 will spawn approval.request; stub state only for now.
            self.write({'state': 'signatory'})
            self.message_post(body=_('Routed to company signatory path.'))
        return True

    def _notify_planner(self, event, reason):
        """Post chatter already done by caller; schedule activity for the planner."""
        self.ensure_one()
        if not self.requester_id:
            return
        if event == 'reject':
            summary = _('Purchase request %s rejected') % self.name
            note = _('Your purchase request %s was rejected.\nReason: %s') % (
                self.name, reason,
            )
        else:
            summary = _('Purchase request %s returned for correction') % self.name
            note = _(
                'Your purchase request %s was returned for correction.\nReason: %s'
            ) % (self.name, reason)
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.requester_id.id,
            summary=summary,
            note=note,
        )
