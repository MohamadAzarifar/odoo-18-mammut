# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_CE_ACTIVE_STATES = ('draft', 'list_pending', 'portal_open', 'opened')
_CE_CREATE_STATES = (
    'inquiry', 'quote_review', 'commission', 'signatory', 'po_ready',
)
_COMM_EXP_ALLOWED_WRITE = {'bid_deadline'}

try:
    from num2fawords import words as _fa_words
except ImportError:  # pragma: no cover - optional at runtime if not installed
    _fa_words = None
    _logger.debug("num2fawords is not installed; Persian amount-in-words unavailable.")


class ZvyClosedEnvelope(models.Model):
    _name = 'zvy.closed.envelope'
    _description = 'Closed Envelope Tender'
    _order = 'id desc'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

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
    holding_company_id = fields.Many2one(
        related='request_id.holding_company_id',
        store=True,
        index=True,
        string='Holding Company',
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
        domain="[('id', 'in', allowed_partner_ids)]",
    )
    allowed_partner_ids = fields.Many2many(
        'res.partner',
        string='Allowed Vendors',
        compute='_compute_allowed_partner_ids',
        depends_context=('uid', 'company'),
        help='Active AVL vendors for this company.',
    )
    opening_datetime = fields.Datetime(string='Opening Datetime', copy=False)
    bid_deadline = fields.Datetime(string='Bid Deadline', copy=False)
    bid_ids = fields.One2many(
        'zvy.closed.envelope.bid',
        'envelope_id',
        string='Bids',
    )
    bid_count = fields.Integer(
        string='Bid Count',
        compute='_compute_bid_count',
    )
    line_ids = fields.Many2many(
        'zvy.purchase.request.line',
        'zvy_closed_envelope_request_line_rel',
        'envelope_id',
        'request_line_id',
        string='Request Lines',
        help='PR lines in scope for this envelope round. Defaults to all lines '
             '(or leftover re-tender lines on a later envelope).',
    )
    winner_partner_id = fields.Many2one(
        'res.partner',
        string='Winner',
        compute='_compute_winner_partner_id',
        store=True,
        help='Set when every awarded item in this envelope shares one vendor.',
    )
    user_can_see_bids = fields.Boolean(
        compute='_compute_user_can_see_bids',
    )
    list_reject_reason = fields.Text(string='List Reject Reason', copy=False)
    published_document_ids = fields.Many2many(
        'ir.attachment',
        'zvy_ce_published_document_rel',
        'envelope_id',
        'attachment_id',
        string='Published Documents',
        help='Tender documents downloadable by invited suppliers on the portal.',
    )

    def _compute_access_url(self):
        super()._compute_access_url()
        for envelope in self:
            envelope.access_url = '/my/tenders/%s' % envelope.id

    @api.depends('bid_ids')
    def _compute_bid_count(self):
        for envelope in self:
            envelope.bid_count = len(envelope.bid_ids)

    @api.depends('bid_ids.line_ids.is_winner', 'bid_ids.partner_id')
    def _compute_winner_partner_id(self):
        for envelope in self:
            winners = envelope.bid_ids.mapped('line_ids').filtered('is_winner')
            partners = winners.mapped('partner_id')
            envelope.winner_partner_id = partners[:1] if len(partners) == 1 else False

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_user_can_see_bids(self):
        user = self.env.user
        is_privileged = self.env.su or user.has_group(
            'zvy_tendering.group_zvy_commission_manager'
        ) or user.has_group('zvy_tendering.group_zvy_tendering_admin')
        for envelope in self:
            envelope.user_can_see_bids = bool(
                is_privileged or envelope.state in ('opened', 'awarded')
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            request = self.env['zvy.purchase.request'].browse(
                vals.get('request_id')
            )
            if request and not self.env.su:
                self._check_can_create_for_request(request, vals)
            if (
                request
                and request.procurement_type != 'tendering'
                and not self.env.su
            ):
                raise UserError(_(
                    'Closed envelopes can only be created for Tendering purchase requests.'
                ))
            if vals.get('name', _('New')) in (False, _('New'), 'New') and request:
                vals['name'] = _('CE/%s') % (request.name or _('New'))
            if request and not vals.get('line_ids'):
                leftover = request.line_ids.filtered('ce_retender')
                scope = leftover if leftover else request.line_ids
                vals['line_ids'] = [(6, 0, scope.ids)]
        envelopes = super().create(vals_list)
        for envelope in envelopes:
            if envelope.request_id:
                envelope.request_id.sudo().write({
                    'closed_envelope_id': envelope.id,
                })
        return envelopes

    @api.model
    def _check_can_create_for_request(self, request, vals):
        if request.state == 'inquiry':
            return
        leftover = request.line_ids.filtered('ce_retender')
        if request.state in _CE_CREATE_STATES and leftover:
            return
        raise UserError(_(
            'Closed envelopes can only be created while the PR is in Inquiry, '
            'or later for leftover items that need re-tender.'
        ))

    def write(self, vals):
        if not self.env.su:
            user = self.env.user
            is_mgr = user.has_group(
                'zvy_tendering.group_zvy_commission_manager'
            ) or user.has_group('zvy_tendering.group_zvy_tendering_admin')
            is_cce = user.has_group(
                'zvy_tendering.group_zvy_commercial_expert'
            )
            is_comm_exp = user.has_group(
                'zvy_tendering.group_zvy_commission_expert'
            )
            if is_comm_exp and not is_mgr and not is_cce:
                extra = set(vals) - _COMM_EXP_ALLOWED_WRITE
                if extra:
                    raise UserError(_(
                        'Commission Experts can only set the bid deadline.'
                    ))
        return super().write(vals)

    def _active_commission_meeting(self):
        """Current non-removed, non-cancelled meeting for this envelope's PR."""
        self.ensure_one()
        if not self.request_id:
            return self.env['zvy.commission.meeting']
        row = self.env['zvy.commission.meeting.case'].sudo().search([
            ('request_id', '=', self.request_id.id),
            ('review_status', '!=', 'removed'),
            ('meeting_id.state', '!=', 'cancelled'),
        ], limit=1, order='id desc')
        return row.meeting_id

    @api.constrains('line_ids', 'state')
    def _check_line_not_on_active_envelope(self):
        for envelope in self:
            if envelope.state not in _CE_ACTIVE_STATES:
                continue
            for line in envelope.line_ids:
                others = line.closed_envelope_ids.filtered(
                    lambda e, current=envelope: (
                        e.id != current.id and e.state in _CE_ACTIVE_STATES
                    )
                )
                if others:
                    raise ValidationError(_(
                        'Line %(product)s is already on an active closed envelope.',
                        product=line.product_id.display_name,
                    ))

    def _invite_partner_domain(self):
        self.ensure_one()
        return self.env['zvy.avl.entry']._avl_partner_domain(self.company_id)

    @api.depends('company_id')
    def _compute_allowed_partner_ids(self):
        Partner = self.env['res.partner']
        Avl = self.env['zvy.avl.entry']
        for envelope in self:
            envelope.allowed_partner_ids = Partner.search(
                Avl._avl_partner_domain(envelope.company_id)
            )

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

    def _portal_partner_matches(self, partner):
        """Whether partner (or its commercial entity) is on the invite list."""
        self.ensure_one()
        if not partner:
            return False
        commercial = partner.commercial_partner_id
        return bool(self.invite_partner_ids.filtered(
            lambda p: p == partner or p.commercial_partner_id == commercial
        ))

    def _portal_invite_partner(self, partner):
        """Return the invite-list partner matching the given portal partner."""
        self.ensure_one()
        if not partner:
            return self.env['res.partner']
        commercial = partner.commercial_partner_id
        return self.invite_partner_ids.filtered(
            lambda p: p == partner or p.commercial_partner_id == commercial
        )[:1]

    def _portal_amount_preview(self, amount):
        """Return formatted currency amount and amount-in-words for portal UI.

        :return: dict with keys ``formatted`` and ``words`` (empty strings if invalid)
        """
        self.ensure_one()
        currency = self.currency_id
        if not currency:
            return {'formatted': '', 'words': ''}
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {'formatted': '', 'words': ''}
        if amount <= 0:
            return {'formatted': '', 'words': ''}

        formatted = currency.format(amount)
        lang = (self.env.lang or '').lower()
        if lang.startswith('fa') and _fa_words is not None:
            words = self._amount_to_persian_words(amount, currency)
        elif currency.name == 'IRR':
            # Avoid core mislabel "Dinar" as IRR unit (use Rial).
            words = self._amount_to_words_with_labels(amount, currency)
        else:
            words = currency.amount_to_text(amount)
        return {'formatted': formatted, 'words': words}

    @api.model
    def _currency_amount_labels(self, currency):
        """Unit/subunit labels for amount-in-words (IRR unit is Rial, not Dinar)."""
        currency.ensure_one()
        if currency.name == 'IRR':
            return _('Rial'), _('Dinar')
        return (
            currency.currency_unit_label or currency.name,
            currency.currency_subunit_label or '',
        )

    @api.model
    def _amount_to_words_with_labels(self, amount, currency):
        """amount_to_text using corrected unit/subunit labels (for IRR)."""
        from odoo import tools
        try:
            from num2words import num2words
        except ImportError:
            unit_label, _subunit = self._currency_amount_labels(currency)
            return '%s %s' % (amount, unit_label)

        def _num2words(number, lang_iso):
            try:
                return num2words(number, lang=lang_iso).title()
            except NotImplementedError:
                return num2words(number, lang='en').title()

        unit_label, subunit_label = self._currency_amount_labels(currency)
        integral, _sep, fractional = f"{amount:.{currency.decimal_places}f}".partition('.')
        integer_value = int(integral)
        lang = tools.get_lang(self.env)
        if currency.is_zero(amount - integer_value):
            return _(
                '%(integral_amount)s %(currency_unit)s',
                integral_amount=_num2words(integer_value, lang.iso_code),
                currency_unit=unit_label,
            )
        return _(
            '%(integral_amount)s %(currency_unit)s and %(fractional_amount)s %(currency_subunit)s',
            integral_amount=_num2words(integer_value, lang.iso_code),
            currency_unit=unit_label,
            fractional_amount=_num2words(int(fractional or 0), lang.iso_code),
            currency_subunit=subunit_label,
        )

    @api.model
    def _amount_to_persian_words(self, amount, currency):
        """Persian amount-in-words using num2fawords + currency unit labels."""
        currency.ensure_one()
        unit_label, subunit_label = self._currency_amount_labels(currency)
        integral, _sep, fractional = f"{amount:.{currency.decimal_places}f}".partition('.')
        integer_value = int(integral)
        fractional_value = int(fractional or 0)
        if currency.is_zero(amount - integer_value):
            return _(
                '%(integral_amount)s %(currency_unit)s',
                integral_amount=_fa_words(integer_value),
                currency_unit=unit_label,
            )
        return _(
            '%(integral_amount)s %(currency_unit)s and %(fractional_amount)s %(currency_subunit)s',
            integral_amount=_fa_words(integer_value),
            currency_unit=unit_label,
            fractional_amount=_fa_words(fractional_value),
            currency_subunit=subunit_label,
        )

    @api.model
    def _get_portal_domain(self, user=None):
        user = user or self.env.user
        partner = user.partner_id.commercial_partner_id
        return [
            ('invite_partner_ids', 'child_of', [partner.id]),
            ('state', 'in', ['portal_open', 'opened', 'awarded', 'cancelled']),
        ]

    def _send_portal_mail(self, template_xmlid, partners, extra_ctx=None):
        """Send a mail.template to each partner (skips partners without email)."""
        self.ensure_one()
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            return
        extra_ctx = extra_ctx or {}
        for partner in partners:
            if not partner.email:
                continue
            template.with_context(
                partner=partner,
                partner_to_id=partner.id,
                **extra_ctx,
            ).send_mail(
                self.id,
                force_send=False,
                email_values={
                    'email_to': partner.email,
                    'recipient_ids': [(4, partner.id)],
                },
            )

    def _notify_invited_partners(self, event, partners=None, clarification_body=None):
        """Notify invitees for portal events (FR-26)."""
        self.ensure_one()
        partners = partners if partners is not None else self.invite_partner_ids
        template_map = {
            'invite': 'zvy_tendering.mail_template_ce_invite',
            'clarification': 'zvy_tendering.mail_template_ce_clarification',
            'awarded': 'zvy_tendering.mail_template_ce_awarded',
            'not_awarded': 'zvy_tendering.mail_template_ce_not_awarded',
            'cancelled': 'zvy_tendering.mail_template_ce_cancelled',
        }
        xmlid = template_map.get(event)
        if not xmlid:
            return
        self._portal_ensure_token()
        self._send_portal_mail(
            xmlid,
            partners,
            extra_ctx={'clarification_body': clarification_body or ''},
        )

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
            if envelope.request_id.state not in _CE_CREATE_STATES:
                raise UserError(_(
                    'The purchase request must be in Inquiry (or a later '
                    'state for re-tender items) to submit a CE list.'
                ))
            if (
                envelope.request_id.state != 'inquiry'
                and not envelope.line_ids.filtered('ce_retender')
            ):
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
        self._portal_ensure_token()
        self.message_post(body=_(
            'Invite list approved; bidding open until %s (opening %s).'
        ) % (self.bid_deadline, self.opening_datetime))
        self._notify_invited_partners('invite')
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
        meeting = self._active_commission_meeting()
        if meeting and meeting.state != 'held':
            raise UserError(_(
                'Bids can only be opened during a held commission meeting.'
            ))
        self.write({'state': 'opened'})
        self.message_post(body=_('Bids unsealed / opened.'))
        return True

    def action_reopen_bidding(self):
        """Extend the bid deadline after it has passed (FR-39 audit)."""
        self.ensure_one()
        self._ensure_commission_manager()
        if self.state != 'portal_open':
            raise UserError(_(
                'Bidding can only be re-opened while the envelope is Portal Open.'
            ))
        now = fields.Datetime.now()
        if not self.bid_deadline or now <= self.bid_deadline:
            raise UserError(_(
                'Bidding can only be re-opened after the deadline has passed.'
            ))
        new_deadline = self.env.context.get('zvy_reopen_deadline')
        if not new_deadline:
            hours = self.company_id.zvy_default_bid_window_hours or 72
            new_deadline = now + timedelta(hours=hours)
        new_deadline = fields.Datetime.to_datetime(new_deadline)
        if new_deadline <= now:
            raise UserError(_('New bid deadline must be in the future.'))
        self.write({'bid_deadline': new_deadline})
        self.message_post(body=_(
            'Bidding re-opened until %s.'
        ) % self.bid_deadline)
        return True

    def action_select_winner(self):
        self.ensure_one()
        self._ensure_commission_manager()
        if self.state != 'opened':
            raise UserError(_(
                'Winner can only be selected after bids are opened.'
            ))
        scope = self.line_ids or self.request_id.line_ids
        winning_lines = self.bid_ids.mapped('line_ids').filtered('is_winner')
        winners_by_line = {}
        for bid_line in winning_lines:
            request_line = bid_line.request_line_id
            if request_line in winners_by_line:
                raise ValidationError(_(
                    'Only one winner is allowed per item on a closed envelope.'
                ))
            if bid_line.partner_id not in self.invite_partner_ids:
                raise ValidationError(_(
                    'Winner must be one of the invited suppliers.'
                ))
            if not bid_line.price_unit:
                raise ValidationError(_(
                    'A winner must have a unit price on %(product)s.',
                    product=request_line.product_id.display_name,
                ))
            winners_by_line[request_line] = bid_line

        pr = self.request_id.sudo()
        awarded_any = bool(winning_lines)
        for request_line in scope:
            bid_line = winners_by_line.get(request_line)
            if bid_line:
                request_line.sudo().write({
                    'awarded_bid_line_id': bid_line.id,
                    'ce_retender': False,
                })
            else:
                request_line.sudo().write({
                    'awarded_bid_line_id': False,
                    'ce_retender': True,
                })

        self.write({'state': 'awarded'})
        if awarded_any and pr.state == 'inquiry':
            pr.write({'state': 'quote_review'})

        winner_partners = winning_lines.mapped('partner_id')
        leftover = any(line.ce_retender for line in scope)
        if awarded_any:
            names = ', '.join(winner_partners.mapped('display_name'))
            if leftover:
                self.message_post(body=_(
                    'Winners selected: %s. Unawarded items returned for re-tender.'
                ) % names)
            else:
                self.message_post(body=_('Winners selected: %s.') % names)
            pr.message_post(body=_(
                'Closed envelope awarded per item: %s.'
            ) % names)
        else:
            self.message_post(body=_(
                'No item awarded; all items returned to CM for re-tender.'
            ))
            pr.message_post(body=_(
                'Closed envelope closed with no winners; items returned for re-tender.'
            ))

        losers = self.invite_partner_ids - winner_partners
        if winner_partners:
            self._notify_invited_partners('awarded', partners=winner_partners)
        if losers:
            self._notify_invited_partners('not_awarded', partners=losers)
        return True

    def action_cancel(self):
        for envelope in self:
            if envelope.state in ('awarded', 'cancelled'):
                raise UserError(_(
                    'Awarded or cancelled envelopes cannot be cancelled again.'
                ))
            envelope.write({'state': 'cancelled'})
            envelope.message_post(body=_('Closed envelope cancelled.'))
            envelope._notify_invited_partners('cancelled')
        return True
    def action_post_clarification(self):
        """Open wizard to post a clarification to invited suppliers."""
        self.ensure_one()
        if self.state not in ('portal_open', 'opened'):
            raise UserError(_(
                'Clarifications can only be posted while bidding is open or bids are opened.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Post Clarification'),
            'res_model': 'zvy.ce.clarification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_envelope_id': self.id,
            },
        }

    def _post_clarification(self, body):
        self.ensure_one()
        body = (body or '').strip()
        if not body:
            raise ValidationError(_('Clarification body is required.'))
        if self.state not in ('portal_open', 'opened'):
            raise UserError(_(
                'Clarifications can only be posted while bidding is open or bids are opened.'
            ))
        self.message_post(
            body=_('Clarification: %s') % body,
            subtype_xmlid='mail.mt_note',
        )
        self._notify_invited_partners('clarification', clarification_body=body)
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
