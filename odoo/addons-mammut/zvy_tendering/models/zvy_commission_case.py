# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from .zvy_purchase_bands import ZVY_VALID_INQUIRY_DAYS


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
        readonly=True,
        ondelete='restrict',
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Requesting Company',
        related='request_id.company_id',
        store=True,
        index=True,
    )
    holding_company_id = fields.Many2one(
        related='request_id.holding_company_id',
        store=True,
        index=True,
        string='Holding Company',
    )
    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('in_review', 'In Review'),
            ('meeting', 'Meeting'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('corrections', 'Corrections'),
            ('returned', 'Returned'),
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
        help='Current commission meeting. History is on meeting agenda rows.',
    )
    meeting_case_ids = fields.One2many(
        'zvy.commission.meeting.case',
        'case_id',
        string='Meeting History',
    )
    precheck_ids = fields.One2many(
        'zvy.commission.precheck',
        'case_id',
        string='Validation Report',
        copy=False,
    )
    precheck_failed = fields.Boolean(
        string='Pre-checks Failed',
        compute='_compute_precheck_failed',
        store=True,
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

    @api.depends('precheck_ids.result')
    def _compute_precheck_failed(self):
        for case in self:
            case.precheck_failed = any(
                row.result == 'fail' for row in case.precheck_ids
            )

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
        return {
            'name': _('Assign Commission Experts'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.commission.assign.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_case_id': self.id},
        }

    def _action_assign_experts(self, expert_ids):
        """Assign commission experts, create missing reviews, and start review.

        :param expert_ids: list of res.users ids
        """
        self.ensure_one()
        self._ensure_manager()
        if self.state not in ('open', 'in_review', 'meeting'):
            raise UserError(_(
                'Experts can only be assigned on open, in-review, or meeting cases.'
            ))
        if not expert_ids:
            raise ValidationError(_(
                'Select at least one Commission Expert before assigning.'
            ))
        self.write({'expert_user_ids': [(6, 0, expert_ids)]})
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

    def action_approve_without_meeting(self):
        self.ensure_one()
        self._ensure_manager()
        if self.state not in ('open', 'in_review', 'meeting'):
            raise UserError(_(
                'Approve without meeting is only available on open, in-review, '
                'or meeting cases.'
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
        return {
            'name': _('Request Corrections'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.commission.corrections.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_case_id': self.id},
        }

    def _action_manager_corrections(self, reason):
        self.ensure_one()
        self._ensure_manager()
        if self.state not in ('in_review', 'meeting'):
            raise UserError(_(
                'Corrections can only be requested from in-review or meeting.'
            ))
        if not reason or not str(reason).strip():
            raise ValidationError(_('A return reason is required.'))
        reason = str(reason).strip()
        self.write({
            'state': 'corrections',
            'manager_decision': 'corrections',
            'manager_notes': reason,
        })
        pr = self.request_id.sudo()
        pr._action_return_from_commission(reason)
        self.message_post(body=_(
            'Corrections requested: %s'
        ) % reason)
        return True

    def _action_manager_approve(self):
        self.ensure_one()
        self.write({
            'state': 'approved',
            'manager_decision': 'approve',
        })
        pr = self.request_id.sudo()
        pr.message_post(body=_(
            'Holding Commission approved (%s).'
        ) % self.name)
        if pr.procurement_type == 'enquiry':
            pr.write({'state': 'po_ready'})
            self.message_post(body=_('Case approved; PR advanced to PO Ready.'))
        else:
            pr._action_spawn_signatory_approval()
            self.message_post(body=_('Case approved; PR advanced to signatory.'))
        return True

    def _precheck_review_datetime(self):
        self.ensure_one()
        meeting = self.meeting_id
        if meeting and meeting.datetime:
            return fields.Datetime.to_datetime(meeting.datetime)
        return fields.Datetime.now()

    def _run_enquiry_prechecks(self):
        """Compute US-06 checks 1–10, replace the Validation Report, return True on hard fail."""
        self.ensure_one()
        self.precheck_ids.unlink()
        if self.request_id.procurement_type != 'enquiry':
            return False
        specs = [
            (1, _('PR date vs notice window'), self._precheck_notice_window),
            (2, _('Proforma / inquiry age'), self._precheck_inquiry_age),
            (3, _('SAP product master data'), self._precheck_sap_product),
            (4, _('Valid inquiries or formalities'), self._precheck_inquiry_or_formalities),
            (5, _('Dossier complete'), self._precheck_dossier),
            (6, _('Vendors on AVL'), self._precheck_avl),
            (7, _('Arithmetic totals'), self._precheck_arithmetic),
            (8, _('Lowest valid selected'), self._precheck_lowest_award),
            (9, _('Prior signature chain'), self._precheck_signature_chain),
            (10, _('SAP split count'), self._precheck_sap_split),
        ]
        Precheck = self.env['zvy.commission.precheck'].sudo()
        vals_list = []
        for sequence, name, method in specs:
            result, message = method()
            vals_list.append({
                'case_id': self.id,
                'sequence': sequence,
                'name': name,
                'result': result,
                'message': message,
            })
        Precheck.create(vals_list)
        self.env.flush_all()
        self.invalidate_recordset(['precheck_ids', 'precheck_failed'])
        return self.precheck_failed

    def _precheck_failed_comment(self):
        self.ensure_one()
        failed = self.precheck_ids.filtered(lambda r: r.result == 'fail').sorted(
            'sequence'
        )
        lines = [
            'Check %s (%s): %s' % (row.sequence, row.name, row.message or '')
            for row in failed
        ]
        return _(
            'Holding Commission validation failed; returned to the requesting '
            'Commercial Manager.<br/>%s'
        ) % '<br/>'.join(lines)

    def _precheck_notice_window(self):
        request = self.request_id
        window = request.company_id._zvy_holding_company().zvy_commission_notice_days or 0
        if window <= 0:
            return 'pass', _(
                'No minimum notice window is configured (placeholder until '
                'the commission-laws document).'
            )
        pr_dt = fields.Datetime.to_datetime(request.create_date)
        review_dt = self._precheck_review_datetime()
        delta = (review_dt.date() - pr_dt.date()).days
        if delta < window:
            return 'fail', _(
                'PR date %(pr)s is only %(days)s day(s) before the commission '
                'review date %(review)s; minimum notice is %(window)s day(s).',
                pr=pr_dt.date(),
                days=delta,
                review=review_dt.date(),
                window=window,
            )
        return 'pass', _(
            'PR date is %(days)s day(s) before the review date (minimum %(window)s).',
            days=delta,
            window=window,
        )

    def _precheck_inquiry_age(self):
        review_dt = self._precheck_review_datetime()
        cutoff = review_dt - timedelta(days=ZVY_VALID_INQUIRY_DAYS)
        stale = []
        for quote in self.request_id.quote_ids:
            if quote.state == 'rejected' or not quote._is_priced():
                continue
            received = quote.received_date or quote.create_date
            received = fields.Datetime.to_datetime(received) if received else False
            if received and received < cutoff:
                stale.append(quote.partner_id.display_name)
        if stale:
            return 'fail', _(
                'Priced inquiries older than %(days)s days vs the commission '
                'review date: %(vendors)s.',
                days=ZVY_VALID_INQUIRY_DAYS,
                vendors=', '.join(stale),
            )
        return 'pass', _(
            'All priced, non-rejected inquiries are within %(days)s days of '
            'the commission review date.',
            days=ZVY_VALID_INQUIRY_DAYS,
        )

    def _precheck_sap_product(self):
        return 'skipped', _(
            'SAP product code/description check is not integrated; skipped.'
        )

    def _precheck_inquiry_or_formalities(self):
        request = self.request_id

        def dossier_count(line):
            # Include rejected quotes: after award, losers are rejected and
            # `_valid_inquiry_count` would drop them below 3.
            return len(line.quote_ids.filtered(
                lambda q: q.state != 'draft' and q._is_priced()
            ))

        short = request.line_ids.filtered(
            lambda l: not l.sole_source and dossier_count(l) < 3
        )
        if not short:
            return 'pass', _(
                'Every line has at least 3 priced inquiries, or is sole source.'
            )
        approval = request.approval_request_id
        formality_job = request.company_id.sudo().zvy_signatory_formalities_job_id
        formality_users = (
            request.company_id._zvy_users_from_job(formality_job, require_users=False)
            if formality_job else self.env['res.users']
        )
        approver_users = approval.approver_ids.mapped('user_id') if approval else self.env['res.users']
        signed = bool(
            approval
            and approval.request_status == 'approved'
            and formality_users
            and all(user in approver_users for user in formality_users)
        )
        if signed:
            return 'pass', _(
                'Fewer than 3 priced inquiries on some lines; formalities '
                'signatures are complete.'
            )
        names = ', '.join(short.mapped('product_id.display_name'))
        return 'fail', _(
            'Lines without 3 priced inquiries and without a completed '
            'formalities signature chain: %s.'
        ) % names

    def _precheck_dossier(self):
        request = self.request_id
        company = request.company_id._zvy_holding_company()
        missing = []
        if company.zvy_commission_require_proforma:
            awarded = request.line_ids.mapped('awarded_quote_id')
            without = awarded.filtered(lambda q: not q.proforma)
            if without:
                missing.append(_(
                    'proforma on awarded quote(s) %s'
                ) % ', '.join(without.mapped('partner_id.display_name')))
        if (
            company.zvy_commission_require_comparison
            and not request.commission_comparison_attachment_ids
        ):
            missing.append(_('comparison document'))
        if (
            company.zvy_commission_require_technical
            and not request.commission_technical_attachment_ids
        ):
            missing.append(_('technical request'))
        if missing:
            return 'fail', _('Dossier incomplete: %s.') % '; '.join(missing)
        if not (
            company.zvy_commission_require_proforma
            or company.zvy_commission_require_comparison
            or company.zvy_commission_require_technical
        ):
            return 'pass', _('No additional dossier documents are required.')
        return 'pass', _('Required dossier attachments are present.')

    def _precheck_avl(self):
        Quote = self.env['zvy.quote']
        missing = []
        for quote in self.request_id.quote_ids:
            allowed = self.env['res.partner'].search(
                Quote._partner_domain_for_line(quote.line_id)
            )
            if quote.partner_id not in allowed:
                missing.append(_(
                    '%(vendor)s on %(product)s',
                    vendor=quote.partner_id.display_name,
                    product=quote.line_id.product_id.display_name,
                ))
        if missing:
            return 'fail', _(
                'Vendors not on the active AVL for the product: %s.'
            ) % '; '.join(missing)
        return 'pass', _('All inquired vendors are on the active AVL.')

    def _precheck_arithmetic(self):
        request = self.request_id
        rounding = request.currency_id.rounding or 0.01
        mismatches = []
        for quote in request.quote_ids:
            if not quote._is_priced():
                continue
            expected = (quote.price_unit or 0.0) * (quote.product_uom_qty or 0.0)
            if float_compare(quote.amount_total, expected, precision_rounding=rounding) != 0:
                mismatches.append(_(
                    '%(vendor)s: unit × qty = %(expected)s, stored total %(total)s',
                    vendor=quote.partner_id.display_name,
                    expected=expected,
                    total=quote.amount_total,
                ))
        line_sum = sum(request.line_ids.mapped('price_subtotal'))
        if float_compare(request.amount_total, line_sum, precision_rounding=rounding) != 0:
            mismatches.append(_(
                'PR total %(total)s does not equal line sum %(sum)s',
                total=request.amount_total,
                sum=line_sum,
            ))
        if mismatches:
            return 'fail', _('Arithmetic mismatch: %s.') % '; '.join(mismatches)
        return 'pass', _('Unit × quantity matches stored totals.')

    def _precheck_lowest_award(self):
        unjustified = []
        for line in self.request_id.line_ids:
            awarded = line.awarded_quote_id
            if not awarded:
                unjustified.append(_(
                    '%s has no awarded quote'
                ) % line.product_id.display_name)
                continue
            if (
                not line._quote_is_lowest_price(awarded)
                and not (line.award_not_lowest_reason or '').strip()
            ):
                unjustified.append(line.product_id.display_name)
        if unjustified:
            return 'fail', _(
                'Award is not the lowest valid quote and no written reason: %s.'
            ) % ', '.join(unjustified)
        return 'pass', _('Awarded quotes are the lowest, or a written reason is stored.')

    def _precheck_signature_chain(self):
        approval = self.request_id.approval_request_id
        if not approval or approval.request_status != 'approved':
            return 'fail', _(
                'Enquiry purchase request cannot enter Holding Commission '
                'until the company signature chain is approved.'
            )
        return 'pass', _('Current company signature chain is approved.')

    def _precheck_sap_split(self):
        return 'skipped', _(
            'SAP split-count / artificial PR-split check is not integrated; skipped.'
        )
