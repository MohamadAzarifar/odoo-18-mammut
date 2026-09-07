# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command

_INTAKE_EDITABLE_STATES = ('draft', 'correction')
_CM_INTAKE_STATES = ('submitted', 'cm_review')
_SIGNATORY_EFFECTIVE_PR_KEYS = {'purchase_nature'}
_ALLOWED_TRANSITIONS = {
    'draft': {'submitted'},
    'correction': {'submitted'},
    'submitted': {'rejected', 'correction', 'inquiry'},
    'cm_review': {'rejected', 'correction', 'inquiry', 'signatory'},
    'inquiry': {'quote_review'},
    'quote_review': {'inquiry', 'commission', 'signatory'},
    'commission': {'signatory', 'quote_review', 'po_ready', 'cm_review'},
    'signatory': {'po_ready', 'cm_review', 'commission'},
    'po_ready': {'done', 'rejected'},
}
_REJECTABLE_STATES = _CM_INTAKE_STATES + ('po_ready',)


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
    commission_comparison_attachment_ids = fields.Many2many(
        'ir.attachment',
        'zvy_pr_comparison_attachment_rel',
        'request_id',
        'attachment_id',
        string='Comparison Documents',
        help='Price comparison dossier for Holding Commission (FR-43 check 5).',
    )
    commission_technical_attachment_ids = fields.Many2many(
        'ir.attachment',
        'zvy_pr_technical_attachment_rel',
        'request_id',
        'attachment_id',
        string='Technical Request Documents',
        help='Technical request dossier for Holding Commission (FR-43 check 5).',
    )
    commission_require_comparison = fields.Boolean(
        related='company_id.zvy_commission_require_comparison',
    )
    commission_require_technical = fields.Boolean(
        related='company_id.zvy_commission_require_technical',
    )
    closed_envelope_id = fields.Many2one(
        'zvy.closed.envelope',
        string='Closed Envelope',
        copy=False,
        readonly=True,
        help='Latest closed envelope on this request.',
    )
    closed_envelope_ids = fields.One2many(
        'zvy.closed.envelope',
        'request_id',
        string='Closed Envelopes',
    )
    award_partner_id = fields.Many2one(
        'res.partner',
        string='Awarded Vendor',
        compute='_compute_award_partner_id',
        store=True,
        help='Set when every awarded (non-re-tender) line shares one vendor.',
    )
    has_ce_retender = fields.Boolean(
        string='Has Re-tender Lines',
        compute='_compute_has_ce_retender',
        store=True,
    )
    approval_request_id = fields.Many2one(
        'approval.request',
        string='Signatory Approval',
        copy=False,
        readonly=True,
    )
    approval_request_ids = fields.One2many(
        'approval.request',
        'zvy_purchase_request_id',
        string='Signatory Approvals',
        copy=False,
        readonly=True,
    )
    approval_request_count = fields.Integer(
        compute='_compute_approval_request_count',
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
    purchase_nature = fields.Selection(
        selection=[
            ('operational', 'Operational'),
            ('non_operational', 'Non-Operational'),
        ],
        string='Purchase Nature',
        required=True,
        default='operational',
        tracking=True,
        help='Selects the operational or non-operational purchase-level table.',
    )
    amount_for_level = fields.Monetary(
        string='Amount for Purchase Level',
        currency_field='currency_id',
        compute='_compute_amount_for_level',
        store=True,
        help='Awarded quote totals when awarded, otherwise line estimates.',
    )
    purchase_level = fields.Selection(
        selection=[
            ('minor', 'Minor'),
            ('medium', 'Medium'),
            ('major', 'Major'),
            ('large', 'Large'),
        ],
        string='Purchase Level',
        compute='_compute_purchase_level',
        store=True,
        help='Computed from amount for level vs company scale and purchase nature (FR-32).',
    )
    is_formalities = fields.Boolean(
        string='Formalities',
        compute='_compute_is_formalities',
        store=True,
        help='True on Enquiry PRs when any line has fewer than 3 valid inquiries (FR-34).',
    )
    is_high_value = fields.Boolean(
        string='High Value',
        compute='_compute_routing_flags',
        store=True,
        help='True when purchase level is large. Qualifies for Holding Commission '
             '(enquiry only after signatures; tendering before signatures, FR-35).',
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
    parent_request_id = fields.Many2one(
        related='split_from_id',
        string='Parent Request',
        store=True,
        help='Customer parentRequestId: original request after a mixed-procurement split.',
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

    @api.depends('approval_request_ids')
    def _compute_approval_request_count(self):
        for request in self:
            request.approval_request_count = len(request.sudo().approval_request_ids)

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for request in self:
            request.amount_total = sum(request.line_ids.mapped('price_subtotal'))

    @api.depends(
        'line_ids.awarded_quote_id',
        'line_ids.awarded_quote_id.amount_total',
        'line_ids.awarded_bid_line_id',
        'line_ids.awarded_bid_line_id.final_price',
        'line_ids.product_uom_qty',
        'line_ids.price_subtotal',
    )
    def _compute_amount_for_level(self):
        for request in self:
            total = 0.0
            for line in request.line_ids:
                if line.awarded_quote_id:
                    total += line.awarded_quote_id.amount_total
                elif line.awarded_bid_line_id:
                    total += (
                        line.awarded_bid_line_id.final_price
                        * (line.product_uom_qty or 0.0)
                    )
                else:
                    total += line.price_subtotal
            request.amount_for_level = total

    @api.depends(
        'line_ids.awarded_partner_id',
        'line_ids.ce_retender',
    )
    def _compute_award_partner_id(self):
        for request in self:
            awarded = request.line_ids.filtered(
                lambda l: l.awarded_partner_id and not l.ce_retender
            )
            partners = awarded.mapped('awarded_partner_id')
            request.award_partner_id = partners[:1] if len(partners) == 1 else False

    @api.depends('line_ids.ce_retender')
    def _compute_has_ce_retender(self):
        for request in self:
            request.has_ce_retender = any(request.line_ids.mapped('ce_retender'))

    @api.depends(
        'amount_for_level',
        'purchase_nature',
        'company_id',
        'company_id.zvy_company_scale',
        'company_id.zvy_use_custom_bands',
        'company_id.zvy_op_minor_max',
        'company_id.zvy_op_medium_max',
        'company_id.zvy_op_major_max',
        'company_id.zvy_op_large_ceo_max',
        'company_id.zvy_nop_minor_max',
        'company_id.zvy_nop_medium_max',
        'company_id.zvy_nop_major_max',
        'company_id.zvy_nop_large_ceo_max',
    )
    def _compute_purchase_level(self):
        for request in self:
            company = request.company_id
            if not company:
                request.purchase_level = 'minor'
                continue
            request.purchase_level = company._zvy_purchase_level(
                request.amount_for_level,
                request.purchase_nature or 'operational',
            )

    @api.depends(
        'procurement_type',
        'line_ids',
        'line_ids.quote_ids',
        'line_ids.quote_ids.state',
        'line_ids.quote_ids.price_unit',
        'line_ids.quote_ids.received_date',
    )
    def _compute_is_formalities(self):
        for request in self:
            if request.procurement_type != 'enquiry':
                request.is_formalities = False
                continue
            lines = request.line_ids
            request.is_formalities = bool(lines) and any(
                line._valid_inquiry_count() < 3 for line in lines
            )

    @api.depends(
        'purchase_level',
        'line_ids.is_commission_item',
        'line_ids.sole_source',
    )
    def _compute_routing_flags(self):
        for request in self:
            request.is_high_value = request.purchase_level == 'large'
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
                # FR-35 / US-06 check 9: enquiry cannot enter commission without
                # an approved first signature chain (full report is Phase 12).
                if (
                    new_state == 'commission'
                    and request.procurement_type == 'enquiry'
                ):
                    approval = request.approval_request_id
                    if vals.get('approval_request_id'):
                        approval = self.env['approval.request'].browse(
                            vals['approval_request_id']
                        )
                    if not approval or approval.request_status != 'approved':
                        raise UserError(_(
                            'Enquiry purchase request %(name)s cannot enter '
                            'Holding Commission until the company signature '
                            'chain is approved.',
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
            'parent_request_id',
            'commission_comparison_attachment_ids',
            'commission_technical_attachment_ids',
        }
        if content_keys and not self.env.su:
            locked = self.filtered(lambda r: r.state not in _INTAKE_EDITABLE_STATES)
            if locked:
                signatory_nature = (
                    content_keys <= _SIGNATORY_EFFECTIVE_PR_KEYS
                    and self._user_is_cm_or_admin()
                    and all(r.state == 'signatory' for r in locked)
                )
                if not signatory_nature:
                    raise UserError(_(
                        'Purchase request %(name)s can only be edited in Draft or Correction.',
                        name=locked[0].name,
                    ))
        res = super().write(vals)
        if set(vals) & _SIGNATORY_EFFECTIVE_PR_KEYS:
            self._zvy_reset_signatory_if_effective_change()
        return res

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
        if self.state not in _REJECTABLE_STATES:
            raise UserError(_(
                'Only submitted, CM-review, or PO-ready requests can be rejected.'
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
        if self.procurement_type != 'tendering':
            raise UserError(_(
                'Closed envelopes can only be created for Tendering purchase requests.'
            ))
        needed = self._ce_lines_needing_envelope()
        active = self.closed_envelope_ids.filtered(
            lambda e: e.state in (
                'draft', 'list_pending', 'portal_open', 'opened',
            )
        )
        if needed:
            if self.state not in (
                'inquiry', 'quote_review', 'commission', 'signatory', 'po_ready',
            ):
                raise UserError(_(
                    'Closed envelopes can only be created while the PR is in '
                    'Inquiry, or later for leftover re-tender items.'
                ))
            self._check_can_create_closed_envelope()
            envelope = self.env['zvy.closed.envelope'].sudo().create({
                'request_id': self.id,
                'line_ids': [(6, 0, needed.ids)],
            })
            return self._action_open_closed_envelope(envelope)
        target = active[:1] or self.closed_envelope_id
        if target:
            return self._action_open_closed_envelope(target)
        if self.state != 'inquiry':
            raise UserError(_(
                'Closed envelopes can only be created while the PR is in Inquiry.'
            ))
        self._check_can_create_closed_envelope()
        envelope = self.env['zvy.closed.envelope'].sudo().create({
            'request_id': self.id,
        })
        return self._action_open_closed_envelope(envelope)

    def _check_can_create_closed_envelope(self):
        self.ensure_one()
        if self._user_is_assigned_expert() or self.env.su:
            return
        is_cm = self.env.user.has_group(
            'zvy_tendering.group_zvy_commercial_manager'
        )
        is_admin = self.env.user.has_group(
            'zvy_tendering.group_zvy_tendering_admin'
        )
        if not (is_cm or is_admin):
            raise UserError(_(
                'Only assigned Commercial Experts can create a closed envelope.'
            ))

    def _action_open_closed_envelope(self, envelope):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Closed Envelope'),
            'res_model': 'zvy.closed.envelope',
            'res_id': envelope.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _ce_lines_needing_envelope(self):
        """PR lines that still need a new CE (leftover re-tender, not on an active CE)."""
        self.ensure_one()
        leftover = self.line_ids.filtered('ce_retender')
        if not leftover:
            return leftover
        active_states = ('draft', 'list_pending', 'portal_open', 'opened')
        return leftover.filtered(
            lambda l: not l.closed_envelope_ids.filtered(
                lambda e: e.state in active_states
            )
        )

    def _ce_award_satisfies_inquiry(self):
        self.ensure_one()
        return any(self.sudo().line_ids.mapped('awarded_bid_line_id'))

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
        else:
            missing = self.sudo().line_ids.filtered(
                lambda l: not l.ce_retender and not l.awarded_bid_line_id
            )
            if missing:
                raise ValidationError(_(
                    'Select a winner on every awarded item before approving. '
                    'Missing: %s'
                ) % ', '.join(missing.mapped('product_id.display_name')))
        self.message_post(body=_('Quotes approved; routing purchase request.'))
        result = self._action_route_after_quotes()
        if not self._ce_award_satisfies_inquiry():
            for line in self.sudo().line_ids:
                awarded = line.awarded_quote_id
                line.quote_ids.filtered(
                    lambda q: q.state == 'submitted' and q != awarded
                ).sudo().write({'state': 'rejected'})
        return result

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
        if self.state not in _REJECTABLE_STATES:
            raise UserError(_(
                'Only submitted, CM-review, or PO-ready requests can be rejected.'
            ))
        if self.state == 'po_ready':
            self.sudo().line_ids.filtered(
                lambda l: l.purchase_state == 'pending'
            ).write({'purchase_state': 'cancelled'})
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
        reason = reason.strip()
        self.write({
            'state': 'correction',
            'return_reason': reason,
        })
        self.message_post(body=_(
            'Returned for correction to planner: %s'
        ) % reason)
        self._notify_planner('return', reason)

    def _action_return_to_expert(self, reason, line_assignments=None):
        """CM destination expert: reopen inquiry so quotes / CE list are editable."""
        self.ensure_one()
        if not reason or not reason.strip():
            raise ValidationError(_('A return reason is required.'))
        if self.state != 'cm_review':
            raise UserError(_(
                'Only CM-review requests can be returned to a commercial expert.'
            ))
        reason = reason.strip()
        if line_assignments:
            for line in self.line_ids:
                expert_ids = line_assignments.get(line.id, [])
                if not expert_ids:
                    raise ValidationError(_(
                        'Assign at least one Commercial Expert to every line.'
                    ))
                line.write({'expert_user_ids': [(6, 0, expert_ids)]})
        missing = self.line_ids.filtered(lambda l: not l.expert_user_ids)
        if missing:
            raise ValidationError(_(
                'Every line must have a Commercial Expert before returning '
                'to inquiry.'
            ))
        self.quote_ids.filtered(
            lambda q: q.state in ('submitted', 'accepted')
        ).sudo().write({'state': 'draft'})
        self.sudo().line_ids.write({
            'awarded_quote_id': False,
            'awarded_bid_line_id': False,
            'ce_retender': False,
        })
        envelopes = self.closed_envelope_ids.filtered(
            lambda e: e.state in (
                'draft', 'list_pending', 'portal_open', 'opened', 'awarded',
            )
        )
        if envelopes:
            envelopes.sudo().write({'state': 'draft'})
        self.write({
            'state': 'inquiry',
            'return_reason': reason,
        })
        self.message_post(body=_(
            'Returned to commercial expert (inquiry): %s'
        ) % reason)
        experts = self.line_ids.mapped('expert_user_ids')
        for expert in experts:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=expert.id,
                summary=_('Correction requested on %s') % self.name,
                note=_(
                    'Purchase request %s was returned for inquiry correction.\n'
                    'Reason: %s'
                ) % (self.name, reason),
            )
        return True

    def _action_return_from_commission(self, reason):
        """Bounce commission corrections to last signatory, or CM if none (FR-45)."""
        self.ensure_one()
        if not reason or not reason.strip():
            raise ValidationError(_('A return reason is required.'))
        if self.state != 'commission':
            raise UserError(_(
                'Only commission requests can be returned from Holding Commission.'
            ))
        reason = reason.strip()
        self.write({'return_reason': reason})
        approval = self.approval_request_id
        if approval and approval.request_status == 'approved':
            self._action_spawn_signatory_approval(resume_commission=True)
            dest = _('last company signatory')
        else:
            self.write({'state': 'cm_review'})
            dest = _('Commercial Manager')
        self.message_post(body=_(
            'Holding Commission requested corrections; returned to %(dest)s.\n'
            'Reason: %(reason)s'
        ) % {'dest': dest, 'reason': reason})
        return True

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
        lines = self.sudo().line_ids
        if not lines:
            return False
        if any(line.ce_retender for line in lines):
            return False
        if self._ce_award_satisfies_inquiry():
            return all(line.awarded_bid_line_id for line in lines)
        return all(line.awarded_quote_id for line in lines)

    def _user_is_cm_or_admin(self):
        return (
            self.env.su
            or self.env.user.has_group('zvy_tendering.group_zvy_commercial_manager')
            or self.env.user.has_group('zvy_tendering.group_zvy_tendering_admin')
        )

    def _user_can_create_po(self):
        return (
            self._user_is_cm_or_admin()
            or self.env.user.has_group(
                'zvy_tendering.group_zvy_commission_manager'
            )
        )

    def _needs_holding_commission(self):
        """Need Commission or large purchase level (FR-35)."""
        self.ensure_one()
        return self.is_commission_item or self.purchase_level == 'large'

    def _action_open_commission_case(self):
        """Create or reopen a Holding Commission case and set state commission."""
        self.ensure_one()
        Case = self.env['zvy.commission.case'].sudo()
        case = self.commission_case_id.sudo()
        if case and case.state in ('corrections', 'returned'):
            case.write({
                'state': 'open',
                'reason_high_value': self.is_high_value,
                'reason_commission_item': self.is_commission_item,
                'manager_decision': False,
            })
        else:
            case = Case.create({
                'request_id': self.id,
                'reason_high_value': self.is_high_value,
                'reason_commission_item': self.is_commission_item,
            })
        self.write({'commission_case_id': case.id})
        if (
            self.procurement_type == 'enquiry'
            and case._run_enquiry_prechecks()
        ):
            comment = case._precheck_failed_comment()
            case.write({'state': 'returned'})
            if self.state != 'cm_review':
                self.write({'state': 'cm_review'})
            self.message_post(body=comment)
            case.message_post(body=comment)
            return case
        self.write({'state': 'commission'})
        self.message_post(body=_(
            'Routed to Holding Commission (%s).'
        ) % case.name)
        return case

    def _action_route_after_quotes(self):
        """FR-35 enquiry: always signatory first. FR-27 tendering: commission-first when needed."""
        self.ensure_one()
        if self.procurement_type == 'enquiry':
            self._action_spawn_signatory_approval()
            return True
        if self._needs_holding_commission():
            self._action_open_commission_case()
        else:
            self._action_spawn_signatory_approval()
        return True

    def _action_route_after_signatory(self):
        """After the current chain is approved: enquiry may still need commission."""
        self.ensure_one()
        if (
            self.procurement_type == 'enquiry'
            and self._needs_holding_commission()
        ):
            self._action_open_commission_case()
            return True
        self.write({'state': 'po_ready'})
        self.message_post(body=_(
            'Signatory approval completed (%s); ready for PO creation.'
        ) % (self.approval_request_id.display_name if self.approval_request_id else ''))
        return True

    def _action_spawn_signatory_approval(self, resume_commission=False):
        """Create sequential approval.request from level + formalities (FR-12/14/32/34)."""
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

        band_users = self.company_id._zvy_signatory_users(
            self.purchase_level,
            self.amount_for_level,
            self.purchase_nature or 'operational',
        )
        if not band_users:
            raise UserError(_(
                'Configure signatories for purchase level "%(level)s" on the company.',
                level=self.purchase_level or _('unknown'),
            ))
        chain_users = list(band_users)
        if self.is_formalities:
            for user in self.company_id.zvy_signatory_formalities_ids:
                if user not in chain_users:
                    chain_users.append(user)
        if not chain_users and not (
            self.has_sole_source and self.company_id.zvy_sole_source_approver_ids
        ):
            raise UserError(_(
                'Cannot spawn signatory approval without any approvers.'
            ))

        Approval = self.env['approval.request'].sudo()
        request = Approval.create({
            'name': _('Signatory: %s') % self.name,
            'category_id': category.id,
            'request_owner_id': self.env.user.id,
            'reference': self.name,
            'amount': self.amount_for_level,
            'reason': self.description or '',
            'zvy_purchase_request_id': self.id,
            'zvy_resume_commission': bool(resume_commission),
        })
        self._zvy_replace_signatory_approvers(request, chain_users)
        if self.has_sole_source:
            self._inject_sole_source_approvers(request)

        if not request.approver_ids:
            raise UserError(_(
                'Cannot spawn signatory approval without any approvers.'
            ))

        request.action_confirm()
        if resume_commission:
            self._zvy_pending_last_signatory(request)
        self.with_context(zvy_skip_signatory_reset=True).write({
            'approval_request_id': request.id,
            'state': 'signatory',
        })
        if resume_commission:
            self.message_post(body=_(
                'Returned to the last company signatory (%s) after '
                'Holding Commission corrections.'
            ) % request.display_name)
        else:
            self.message_post(body=_(
                'Routed to company signatory path (%s).'
            ) % request.display_name)
        return request

    def _zvy_pending_last_signatory(self, approval_request):
        """Leave only the last signatory pending (FR-45 commission bounce).

        Earlier approvers are marked approved so completing the last step
        finishes the document; refuse still bounces to the previous signatory.
        """
        approvers = approval_request.approver_ids.sorted(
            lambda a: (a.sequence, a.id)
        )
        if len(approvers) < 2:
            return
        last = approvers[-1]
        earlier = approvers[:-1]
        approval_request._cancel_activities()
        earlier.sudo().write({'status': 'approved'})
        last.sudo().write({'status': 'pending'})
        last.sudo()._create_activity()

    def _zvy_replace_signatory_approvers(self, approval_request, users):
        """Replace category template approvers with the level / formalities chain."""
        commands = [Command.clear()]
        sequence = 10
        seen = self.env['res.users']
        for user in users:
            if user in seen:
                continue
            seen |= user
            commands.append(Command.create({
                'user_id': user.id,
                'required': True,
                'sequence': sequence,
                'status': 'new',
            }))
            sequence += 10
        approval_request.write({'approver_ids': commands})

    def _zvy_reset_signatory_if_effective_change(self):
        """Archive the in-progress chain and spawn a new one (FR-34)."""
        if self.env.context.get('zvy_skip_signatory_reset'):
            return
        for request in self:
            if request.state != 'signatory':
                continue
            current = request.approval_request_id
            if not current or current.request_status == 'approved':
                continue
            old_name = current.display_name
            if current.request_status in ('new', 'pending'):
                current.sudo().action_cancel()
            request.with_context(
                zvy_skip_signatory_reset=True,
            )._action_spawn_signatory_approval()
            request.message_post(body=_(
                'Effective change reset the signatory chain. Previous approval '
                '%s is kept in history.'
            ) % old_name)

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
        """UI opens the line-selection wizard; RPC creates POs for all pending lines."""
        self.ensure_one()
        self._check_can_create_po()
        if self.env.context.get('zvy_ui_create_po'):
            return self._action_open_create_po_wizard()
        return self._create_purchase_orders()

    def _action_open_create_po_wizard(self):
        self.ensure_one()
        if not self._pending_po_lines():
            raise UserError(_(
                'There are no pending awarded lines to create a purchase order from.'
            ))
        return {
            'name': _('Create Purchase Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.create.po.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def _check_can_create_po(self):
        self.ensure_one()
        if not self._user_can_create_po():
            raise UserError(_(
                'Only Commercial Managers and Commission Managers can create '
                'purchase orders.'
            ))
        if self.state != 'po_ready':
            raise UserError(_(
                'Purchase orders can only be created when the request is PO Ready.'
            ))
        approval = self.sudo().approval_request_id
        if approval and approval.request_status != 'approved':
            raise UserError(_(
                'Signatory approval must be fully approved before creating POs.'
            ))

    def _pending_po_lines(self):
        self.ensure_one()
        lines = self.sudo().line_ids.filtered(
            lambda l: l.purchase_state == 'pending'
        )
        if self._ce_award_satisfies_inquiry():
            return lines.filtered('awarded_bid_line_id')
        return lines.filtered('awarded_quote_id')

    def _check_create_po_lines(self, lines):
        self.ensure_one()
        if not lines:
            raise UserError(_(
                'Select at least one pending line to create a purchase order.'
            ))
        if lines.mapped('request_id') != self:
            raise UserError(_(
                'Purchase order lines must belong to this purchase request.'
            ))
        not_pending = lines.filtered(lambda l: l.purchase_state != 'pending')
        if not_pending:
            raise UserError(_(
                'Only pending lines can be included in a purchase order. '
                'Already processed: %s'
            ) % ', '.join(not_pending.mapped('product_id.display_name')))
        if self._ce_award_satisfies_inquiry():
            missing = lines.filtered(lambda l: not l.awarded_bid_line_id)
            if missing:
                raise UserError(_(
                    'Award data is required before creating purchase orders. '
                    'Missing: %s'
                ) % ', '.join(missing.mapped('product_id.display_name')))
            return
        missing = lines.filtered(lambda l: not l.awarded_quote_id)
        if missing:
            raise UserError(_(
                'Award data is required before creating purchase orders. '
                'Missing: %s'
            ) % ', '.join(missing.mapped('product_id.display_name')))

    def _create_purchase_orders(self, lines=None):
        """Create POs for `lines` (default: all pending awarded lines)."""
        self.ensure_one()
        self._check_can_create_po()
        lines = lines if lines is not None else self._pending_po_lines()
        self._check_create_po_lines(lines)

        request = self.sudo()
        lines = lines.sudo()
        if request._ce_award_satisfies_inquiry():
            orders = request._create_po_from_ce_award(lines)
        else:
            orders = request._create_po_from_awarded_quotes(lines)
        lines.write({'purchase_state': 'ordered'})
        request._sync_state_after_po()
        request.message_post(body=_(
            'Purchase order(s) created: %s'
        ) % ', '.join(orders.mapped('name')))
        return self.action_open_purchase_orders()

    def _sync_state_after_po(self):
        self.ensure_one()
        pending = self.line_ids.filtered(lambda l: l.purchase_state == 'pending')
        if not pending and self.state == 'po_ready':
            self.write({'state': 'done'})

    def _create_po_from_awarded_quotes(self, lines):
        self.ensure_one()
        grouped = defaultdict(lambda: self.env['zvy.purchase.request.line'])
        for line in lines:
            partner = line.awarded_quote_id.partner_id
            if not partner:
                raise UserError(_(
                    'Line %s has no awarded vendor.'
                ) % line.product_id.display_name)
            grouped[partner] |= line

        orders = self.env['purchase.order']
        PurchaseOrder = self.env['purchase.order'].sudo()
        PurchaseLine = self.env['purchase.order.line'].sudo()
        for partner, po_lines in grouped.items():
            po = PurchaseOrder.create(self._prepare_purchase_order_vals(partner))
            for line in po_lines:
                quote = line.awarded_quote_id
                PurchaseLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_qty': line.product_uom_qty,
                    'product_uom': line.product_uom_id.id,
                    'price_unit': quote.price_unit,
                    'date_planned': fields.Datetime.now(),
                    'zvy_purchase_request_line_id': line.id,
                })
            orders |= po
        return orders

    def _create_po_from_ce_award(self, lines):
        self.ensure_one()
        grouped = defaultdict(lambda: self.env['zvy.purchase.request.line'])
        for line in lines:
            partner = line.awarded_partner_id
            if not partner:
                raise UserError(_(
                    'Line %s has no awarded vendor.'
                ) % line.product_id.display_name)
            grouped[partner] |= line

        orders = self.env['purchase.order']
        PurchaseOrder = self.env['purchase.order'].sudo()
        PurchaseLine = self.env['purchase.order.line'].sudo()
        for partner, po_lines in grouped.items():
            po = PurchaseOrder.create(self._prepare_purchase_order_vals(partner))
            for line in po_lines:
                bid_line = line.awarded_bid_line_id
                price_unit = (
                    bid_line.final_price if bid_line else (line.price_estimate or 0.0)
                )
                PurchaseLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.product_id.display_name,
                    'product_qty': line.product_uom_qty,
                    'product_uom': line.product_uom_id.id,
                    'price_unit': price_unit,
                    'date_planned': fields.Datetime.now(),
                    'zvy_purchase_request_line_id': line.id,
                })
            orders |= po
        return orders

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
        orders = self.sudo().purchase_order_ids
        if len(orders) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = orders.id
        return action

    def action_open_approval_request(self):
        self.ensure_one()
        if not self.approval_request_id and not self.approval_request_ids:
            raise UserError(_('No signatory approval is linked to this request.'))
        if len(self.approval_request_ids) > 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Signatory Approvals'),
                'res_model': 'approval.request',
                'view_mode': 'list,form',
                'domain': [('zvy_purchase_request_id', '=', self.id)],
                'context': {'default_zvy_purchase_request_id': self.id},
            }
        approval = self.approval_request_id or self.approval_request_ids[:1]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Signatory Approval'),
            'res_model': 'approval.request',
            'res_id': approval.id,
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
