# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

_INTAKE_EDITABLE_STATES = ('draft', 'correction')
_CM_INTAKE_STATES = ('submitted', 'cm_review')
_ALLOWED_TRANSITIONS = {
    'draft': {'submitted'},
    'correction': {'submitted'},
    'submitted': {'rejected', 'correction', 'inquiry'},
    'cm_review': {'rejected', 'correction', 'inquiry', 'signatory'},
    'inquiry': {'quote_review'},
    'quote_review': {'inquiry', 'commission', 'signatory'},
    'commission': {'signatory', 'quote_review'},
    'signatory': {'po_ready', 'cm_review'},
    'po_ready': {'done'},
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
        readonly=True,
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
    approval_request_id = fields.Many2one(
        'approval.request',
        string='Signatory Approval',
        copy=False,
        readonly=True,
    )
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'zvy_purchase_request_id',
        string='Purchase Orders',
        copy=False,
        readonly=True,
    )
    purchase_order_count = fields.Integer(
        compute='_compute_purchase_order_count',
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
    procurement_type = fields.Selection(
        selection=[
            ('enquiry', 'Enquiry'),
            ('tendering', 'Tendering'),
        ],
        string='Procurement Type',
        compute='_compute_procurement_type',
        store=True,
        help='Set when every line is the same product type. Empty when mixed or there are no lines.',
    )
    is_mixed_procurement = fields.Boolean(
        string='Mixed Enquiry and Tendering',
        compute='_compute_procurement_type',
        store=True,
        help='True when the request has both Enquiry and Tendering product lines.',
    )
    split_from_id = fields.Many2one(
        'zvy.purchase.request',
        string='Split From',
        copy=False,
        readonly=True,
        index=True,
        help='Original request this tendering request was split from.',
    )
    split_request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Split Request',
        copy=False,
        readonly=True,
        help='Tendering request created by splitting mixed lines off this request.',
    )
    reject_reason = fields.Text(copy=False)
    return_reason = fields.Text(copy=False)
    quote_reject_reason = fields.Text(copy=False)

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for request in self:
            request.purchase_order_count = len(request.sudo().purchase_order_ids)

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

    @api.depends('line_ids.procurement_type')
    def _compute_procurement_type(self):
        for request in self:
            types = {line.procurement_type for line in request.line_ids if line.procurement_type}
            request.is_mixed_procurement = len(types) > 1
            request.procurement_type = types.pop() if len(types) == 1 else False

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
            # Requester is always the creating user (not spoofable via RPC/UI).
            if not self.env.su:
                vals['requester_id'] = self.env.user.id
        return super().create(vals_list)

    def write(self, vals):
        if 'requester_id' in vals and not self.env.su:
            raise UserError(_('The requester cannot be changed.'))
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
                # FR-28: no po_ready while linked approval is still pending.
                if new_state == 'po_ready':
                    approval = request.approval_request_id
                    if vals.get('approval_request_id'):
                        approval = self.env['approval.request'].browse(
                            vals['approval_request_id']
                        )
                    if approval and approval.request_status != 'approved':
                        raise UserError(_(
                            'Purchase request %(name)s cannot enter PO Ready '
                            'while signatory approval is still pending.',
                            name=request.name,
                        ))
        # line_ids / quote_ids are exempt: one2many edits (awarded quote, inquiry
        # quotes) write through the parent while the PR is locked. Guards live on
        # zvy.purchase.request.line and zvy.quote.
        content_keys = set(vals) - {
            'state',
            'reject_reason',
            'return_reason',
            'quote_reject_reason',
            'commission_case_id',
            'closed_envelope_id',
            'award_partner_id',
            'approval_request_id',
            'message_main_attachment_id',
            'quote_ids',
            'line_ids',
            'split_from_id',
            'split_request_id',
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
        mixed = self.filtered('is_mixed_procurement')
        if mixed:
            if self.env.context.get('zvy_ui_submit') and len(self) == 1:
                return self._action_open_split_wizard()
            raise ValidationError(_(
                'This purchase request mixes Enquiry and Tendering products. '
                'Split it first with action_split_mixed, then submit each '
                'request separately.'
            ))
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

    def _action_open_split_wizard(self):
        self.ensure_one()
        return {
            'name': _('Split Purchase Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.split.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_split_mixed(self):
        """Move Tendering lines onto a new PR; keep Enquiry lines on this one."""
        self.ensure_one()
        if self.state not in _INTAKE_EDITABLE_STATES:
            raise UserError(_(
                'Only draft or correction requests can be split.'
            ))
        if not self.is_mixed_procurement:
            raise UserError(_(
                'This purchase request does not mix Enquiry and Tendering products.'
            ))
        enquiry_lines = self.line_ids.filtered(
            lambda line: line.procurement_type == 'enquiry'
        )
        tendering_lines = self.line_ids.filtered(
            lambda line: line.procurement_type == 'tendering'
        )
        if not enquiry_lines or not tendering_lines:
            raise UserError(_(
                'Cannot split: both Enquiry and Tendering lines are required.'
            ))
        new_pr = self.sudo().create({
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'description': self.description,
            'requester_id': self.requester_id.id,
            'split_from_id': self.id,
        })
        tendering_lines.sudo().write({'request_id': new_pr.id})
        self.write({'split_request_id': new_pr.id})
        self.message_post(body=_(
            'Tendering lines moved to %(name)s. Submit each request separately.',
            name=new_pr.name,
        ))
        new_pr.message_post(body=_(
            'Created by splitting Tendering lines from %(name)s.',
            name=self.name,
        ))
        return new_pr

    def action_open_split_request(self):
        self.ensure_one()
        target = self.split_request_id or self.split_from_id
        if not target:
            raise UserError(_('This purchase request has no split sibling.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'zvy.purchase.request',
            'res_id': target.id,
            'view_mode': 'form',
            'target': 'current',
        }

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
        if (
            self.procurement_type != 'enquiry'
            and not self._ce_award_satisfies_inquiry()
        ):
            raise UserError(_(
                'Quotes can only be submitted on Enquiry purchase requests.'
            ))
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
        if self.procurement_type != 'tendering':
            raise UserError(_(
                'Closed envelopes can only be created for Tendering purchase requests.'
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
        if not self._ce_award_satisfies_inquiry():
            missing = self.sudo().line_ids.filtered(lambda l: not l.awarded_quote_id)
            if missing:
                raise ValidationError(_(
                    'Select an awarded quote on every line before approving. '
                    'Missing: %s'
                ) % ', '.join(missing.mapped('product_id.display_name')))
            unjustified = self.sudo().line_ids.filtered(
                lambda l: l.awarded_quote_id
                and not l._quote_is_lowest_price(l.awarded_quote_id)
                and not (l.award_not_lowest_reason or '').strip()
            )
            if unjustified:
                raise ValidationError(_(
                    'A reason is required when awarding a quote that is not '
                    'the lowest price. Missing: %s'
                ) % ', '.join(unjustified.mapped('product_id.display_name')))
            for line in self.sudo().line_ids:
                awarded = line.awarded_quote_id
                awarded.sudo().write({'state': 'accepted'})
                line.quote_ids.filtered(
                    lambda q: q.state == 'submitted' and q != awarded
                ).sudo().write({'state': 'rejected'})
        else:
            if not self.award_partner_id:
                raise ValidationError(_(
                    'Closed-envelope award vendor is required before approving.'
                ))
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
        self.sudo().line_ids.write({'awarded_quote_id': False})
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

    def _has_award_data(self):
        self.ensure_one()
        if self._ce_award_satisfies_inquiry():
            return bool(self.award_partner_id)
        lines = self.sudo().line_ids
        return bool(lines) and all(line.awarded_quote_id for line in lines)

    def _user_is_cm_or_admin(self):
        return (
            self.env.su
            or self.env.user.has_group('zvy_tendering.group_zvy_commercial_manager')
            or self.env.user.has_group('zvy_tendering.group_zvy_tendering_admin')
        )

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
            self._action_spawn_signatory_approval()
        return True

    def _action_spawn_signatory_approval(self):
        """Create sequential approval.request and move PR to signatory (FR-12/14)."""
        self.ensure_one()
        category = self.company_id.zvy_signatory_approval_category_id
        if not category:
            raise UserError(_(
                'Configure the Signatory Approval Category on the company '
                'before routing to company signatories.'
            ))
        if not category.approver_sequence:
            raise UserError(_(
                'Signatory Approval Category "%s" must use Approvers Sequence '
                'so signatories approve in order.'
            ) % category.display_name)
        if not category.approver_ids and not (
            self.has_sole_source and self.company_id.zvy_sole_source_approver_ids
        ):
            raise UserError(_(
                'Signatory Approval Category "%s" has no approvers configured.'
            ) % category.display_name)

        Approval = self.env['approval.request'].sudo()
        request = Approval.create({
            'name': _('Signatory: %s') % self.name,
            'category_id': category.id,
            'request_owner_id': self.env.user.id,
            'reference': self.name,
            'amount': self.amount_total,
            'reason': self.description or '',
            'zvy_purchase_request_id': self.id,
        })
        if self.has_sole_source:
            self._inject_sole_source_approvers(request)

        if not request.approver_ids:
            raise UserError(_(
                'Cannot spawn signatory approval without any approvers.'
            ))

        request.action_confirm()
        self.write({
            'approval_request_id': request.id,
            'state': 'signatory',
        })
        self.message_post(body=_(
            'Routed to company signatory path (%s).'
        ) % request.display_name)
        return request

    def _inject_sole_source_approvers(self, approval_request):
        """Ensure company sole-source / CEO approvers are last required in chain."""
        self.ensure_one()
        ceo_users = self.company_id.zvy_sole_source_approver_ids
        if not ceo_users:
            raise UserError(_(
                'Sole-source purchase requests require Sole-Source Approvers '
                'configured on the company (FR-14).'
            ))
        existing = approval_request.approver_ids.mapped('user_id')
        max_seq = max(approval_request.approver_ids.mapped('sequence') or [10])
        commands = []
        seq = max_seq
        for user in ceo_users:
            if user in existing:
                # Mark existing as required and push to the end.
                approver = approval_request.approver_ids.filtered(
                    lambda a, u=user: a.user_id == u
                )[:1]
                seq += 10
                commands.append(Command.update(approver.id, {
                    'required': True,
                    'sequence': seq,
                }))
            else:
                seq += 10
                commands.append(Command.create({
                    'user_id': user.id,
                    'required': True,
                    'sequence': seq,
                    'status': 'new',
                }))
        if commands:
            approval_request.write({'approver_ids': commands})

    def action_resubmit_signatory(self):
        self.ensure_one()
        if not self._user_is_cm_or_admin():
            raise UserError(_(
                'Only Commercial Managers can resubmit to signatories.'
            ))
        if self.state != 'cm_review':
            raise UserError(_(
                'Only CM-review requests can be resubmitted to signatories.'
            ))
        if not self._has_award_data():
            raise UserError(_(
                'Award data is required before resubmitting to signatories.'
            ))
        self._action_spawn_signatory_approval()
        return True

    def action_create_po(self):
        self.ensure_one()
        if not self._user_is_cm_or_admin():
            raise UserError(_(
                'Only Commercial Managers can create purchase orders.'
            ))
        if self.state != 'po_ready':
            raise UserError(_(
                'Purchase orders can only be created when the request is PO Ready.'
            ))
        if not self._has_award_data():
            raise UserError(_(
                'Award data is required before creating purchase orders.'
            ))
        if self.approval_request_id and self.approval_request_id.request_status != 'approved':
            raise UserError(_(
                'Signatory approval must be fully approved before creating POs.'
            ))

        orders = self.env['purchase.order']
        if self._ce_award_satisfies_inquiry():
            orders = self._create_po_from_ce_award()
        else:
            orders = self._create_po_from_awarded_quotes()

        self.write({'state': 'done'})
        self.message_post(body=_(
            'Purchase order(s) created: %s'
        ) % ', '.join(orders.mapped('name')))
        return self.action_open_purchase_orders()

    def _create_po_from_awarded_quotes(self):
        self.ensure_one()
        grouped = defaultdict(lambda: self.env['zvy.purchase.request.line'])
        for line in self.sudo().line_ids:
            partner = line.awarded_quote_id.partner_id
            grouped[partner] |= line

        orders = self.env['purchase.order']
        PurchaseOrder = self.env['purchase.order'].sudo()
        PurchaseLine = self.env['purchase.order.line'].sudo()
        for partner, lines in grouped.items():
            po = PurchaseOrder.create(self._prepare_purchase_order_vals(partner))
            for line in lines:
                quote = line.awarded_quote_id
                PurchaseLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_qty': line.product_uom_qty,
                    'product_uom': line.product_uom_id.id,
                    'price_unit': quote.price_unit,
                    'date_planned': fields.Datetime.now(),
                })
            orders |= po
        return orders

    def _create_po_from_ce_award(self):
        self.ensure_one()
        partner = self.award_partner_id
        PurchaseOrder = self.env['purchase.order'].sudo()
        PurchaseLine = self.env['purchase.order.line'].sudo()
        po = PurchaseOrder.create(self._prepare_purchase_order_vals(partner))

        envelope = self.closed_envelope_id
        winning_bid = envelope.bid_ids.filtered(
            lambda b: b.partner_id == partner
        )[:1]
        lines = self.sudo().line_ids
        for line in lines:
            if len(lines) == 1 and winning_bid and winning_bid.amount:
                price_unit = winning_bid.amount / (line.product_uom_qty or 1.0)
            else:
                price_unit = line.price_estimate or 0.0
            PurchaseLine.create({
                'order_id': po.id,
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'product_qty': line.product_uom_qty,
                'product_uom': line.product_uom_id.id,
                'price_unit': price_unit,
                'date_planned': fields.Datetime.now(),
            })
        return po

    def _prepare_purchase_order_vals(self, partner):
        self.ensure_one()
        return {
            'partner_id': partner.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'origin': self.name,
            'payment_term_id': partner.property_supplier_payment_term_id.id,
            'fiscal_position_id': self.env['account.fiscal.position'].with_company(
                self.company_id
            )._get_fiscal_position(partner).id,
            'zvy_purchase_request_id': self.id,
        }

    def action_open_purchase_orders(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('zvy_purchase_request_id', '=', self.id)],
            'context': {'default_zvy_purchase_request_id': self.id},
        }
        if len(self.purchase_order_ids) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.purchase_order_ids.id
        return action

    def action_open_approval_request(self):
        self.ensure_one()
        if not self.approval_request_id:
            raise UserError(_('No signatory approval is linked to this request.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Signatory Approval'),
            'res_model': 'approval.request',
            'res_id': self.approval_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

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
