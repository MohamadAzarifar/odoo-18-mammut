# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_SIGNATORY_EFFECTIVE_LINE_KEYS = {
    'product_id',
    'product_uom_qty',
    'product_uom_id',
    'price_estimate',
    'awarded_quote_id',
}


class ZvyPurchaseRequestLine(models.Model):
    _name = 'zvy.purchase.request.line'
    _description = 'Purchase Request Line'
    _order = 'id'

    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade',
        index=True,
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
    currency_id = fields.Many2one(related='request_id.currency_id')
    request_state = fields.Selection(
        related='request_id.state',
        string='Request Status',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='restrict',
    )
    product_uom_qty = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        digits='Product Unit of Measure',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        required=True,
    )
    price_estimate = fields.Monetary(
        string='Price Estimate',
        currency_field='currency_id',
        default=0.0,
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        currency_field='currency_id',
        compute='_compute_price_subtotal',
        store=True,
    )
    sole_source = fields.Boolean(
        string='Sole Source',
        compute='_compute_sole_source',
        store=True,
        help='True when the product has exactly one active AVL vendor for the '
             'request company. Forces ≥1 quote and includes CEO in the signatory chain.',
    )
    is_commission_item = fields.Boolean(
        string='Commission Item',
        compute='_compute_procurement_flags',
        store=True,
        help='True when the resolved Enquiry product needs Holding Commission '
             'for this request company (holding overlay, else product default).',
    )
    procurement_type = fields.Selection(
        selection=[
            ('enquiry', 'Enquiry'),
            ('tendering', 'Tendering'),
        ],
        string='Procurement Type',
        compute='_compute_procurement_flags',
        store=True,
        help='Resolved for the request company from a company overlay, else '
             'the product default.',
    )
    expert_user_ids = fields.Many2many(
        'res.users',
        'zvy_pr_line_expert_rel',
        'line_id',
        'user_id',
        string='Commercial Experts',
        domain=lambda self: [
            ('groups_id', 'in', [
                self.env.ref('zvy_tendering.group_zvy_commercial_expert').id,
            ]),
        ],
    )
    quote_ids = fields.One2many(
        'zvy.quote',
        'line_id',
        string='Quotes',
    )
    quote_count = fields.Integer(compute='_compute_quote_count')
    quotes_submitted = fields.Boolean(
        string='Quotes Submitted',
        compute='_compute_quotes_submitted',
        store=True,
        help='Set once the assigned expert submits the quote set for this line.',
    )
    quote_shortfall_reason = fields.Text(
        string='Fewer Quotes Reason',
        copy=False,
        help='Required when submitting fewer than 3 valid inquiries on a '
             'non-sole-source line.',
    )
    awarded_quote_id = fields.Many2one(
        'zvy.quote',
        string='Awarded Quote',
        copy=False,
        domain="[('line_id', '=', id), ('state', 'in', ('submitted', 'accepted'))]",
        help='Winning quote selected by the Commercial Manager in quote review.',
    )
    awarded_bid_line_id = fields.Many2one(
        'zvy.closed.envelope.bid.line',
        string='Awarded Bid Line',
        copy=False,
        help='Winning closed-envelope bid line for this item.',
    )
    ce_retender = fields.Boolean(
        string='Re-tender',
        copy=False,
        help='True when this item had no winner in the last closed envelope '
             'and should return to the Commercial Manager for a later tender.',
    )
    awarded_partner_id = fields.Many2one(
        'res.partner',
        string='Awarded Vendor',
        compute='_compute_awarded_partner_id',
        store=True,
    )
    closed_envelope_ids = fields.Many2many(
        'zvy.closed.envelope',
        'zvy_closed_envelope_request_line_rel',
        'request_line_id',
        'envelope_id',
        string='Closed Envelopes',
    )
    award_not_lowest_reason = fields.Text(
        string='Not Lowest Price Reason',
        copy=False,
        help='Required when the awarded quote is not the lowest unit price '
             'among priced non-draft quotes on this line.',
    )
    last_vendor_id = fields.Many2one(
        'res.partner',
        string='Last Vendor',
        compute='_compute_last_purchase',
        store=True,
        help='Vendor from the latest confirmed PO or awarded inquiry for this '
             'product and company (FR-37).',
    )
    last_price = fields.Monetary(
        string='Last Price',
        currency_field='currency_id',
        compute='_compute_last_purchase',
        store=True,
    )
    last_purchase_date = fields.Date(
        string='Last Purchase Date',
        compute='_compute_last_purchase',
        store=True,
    )
    purchase_state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('ordered', 'Ordered'),
            ('cancelled', 'Cancelled'),
        ],
        string='Purchase State',
        default='pending',
        required=True,
        copy=False,
        index=True,
        help='Pending until included in a PO or cancelled when the request is rejected.',
    )

    @api.depends(
        'awarded_quote_id.partner_id',
        'awarded_bid_line_id.partner_id',
    )
    def _compute_awarded_partner_id(self):
        for line in self:
            line.awarded_partner_id = (
                line.awarded_quote_id.partner_id
                or line.awarded_bid_line_id.partner_id
            )

    @api.depends('product_id', 'product_uom_qty', 'product_uom_id')
    def _compute_display_name(self):
        for line in self:
            product = line.product_id.display_name or _('New')
            qty = line.product_uom_qty
            uom = line.product_uom_id.display_name or ''
            if uom:
                line.display_name = '%s (%s %s)' % (product, qty, uom)
            else:
                line.display_name = '%s (%s)' % (product, qty)

    @api.depends('price_estimate', 'product_uom_qty')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_estimate

    @api.depends('quote_ids')
    def _compute_quote_count(self):
        for line in self:
            line.quote_count = len(line.quote_ids)

    @api.depends('quote_ids.state')
    def _compute_quotes_submitted(self):
        for line in self:
            live = line.quote_ids.filtered(lambda q: q.state != 'rejected')
            line.quotes_submitted = bool(live) and all(
                quote.state != 'draft' for quote in live
            )

    @api.depends(
        'product_id',
        'product_id.zvy_need_commission',
        'product_id.zvy_procurement_type',
        'product_id.product_tmpl_id.zvy_procurement_company_ids',
        'product_id.product_tmpl_id.zvy_procurement_company_ids.company_id',
        'product_id.product_tmpl_id.zvy_procurement_company_ids.procurement_type',
        'product_id.product_tmpl_id.zvy_procurement_company_ids.override_need_commission',
        'product_id.product_tmpl_id.zvy_procurement_company_ids.need_commission',
        'company_id',
        'company_id.root_id',
    )
    def _compute_procurement_flags(self):
        by_company = {}
        for line in self:
            cid = line.company_id.id if line.company_id else False
            by_company.setdefault(cid, self.browse())
            by_company[cid] |= line
        for lines in by_company.values():
            company = lines[0].company_id
            templates = lines.mapped('product_id.product_tmpl_id')
            resolved = (
                templates._zvy_resolve_procurement_map(company) if company else {}
            )
            for line in lines:
                tmpl = line.product_id.product_tmpl_id
                if not tmpl:
                    line.procurement_type = False
                    line.is_commission_item = False
                    continue
                if not company:
                    ptype = tmpl.zvy_procurement_type or False
                    line.procurement_type = ptype
                    line.is_commission_item = bool(
                        ptype == 'enquiry' and tmpl.zvy_need_commission
                    )
                    continue
                ptype, need = resolved.get(
                    tmpl.id,
                    (tmpl.zvy_procurement_type or False, False),
                )
                line.procurement_type = ptype
                line.is_commission_item = bool(need)

    @api.depends('product_id', 'company_id')
    def _compute_sole_source(self):
        Avl = self.env['zvy.avl.entry']
        for line in self:
            if not line.product_id or not line.company_id:
                line.sole_source = False
                continue
            line.sole_source = Avl._avl_partner_count(
                line.company_id, product=line.product_id,
            ) == 1

    @api.depends('product_id', 'company_id', 'request_id')
    def _compute_last_purchase(self):
        for line in self:
            vendor, price, date = line._last_purchase_values()
            line.last_vendor_id = vendor
            line.last_price = price
            line.last_purchase_date = date

    def _last_purchase_values(self):
        """Latest confirmed PO line, else latest awarded quote on another PR."""
        self.ensure_one()
        if not self.product_id or not self.company_id:
            return False, 0.0, False
        pol = self._last_purchase_order_line()
        if pol:
            order = pol.order_id
            when = order.date_approve or order.date_order
            if when:
                when = fields.Date.to_date(when)
            return pol.partner_id, pol.price_unit, when
        other = self._last_awarded_history_line()
        if other and other.awarded_quote_id:
            quote = other.awarded_quote_id
            when = quote.received_date or quote.create_date
            if when:
                when = fields.Date.to_date(when)
            return quote.partner_id, quote.price_unit, when
        return False, 0.0, False

    def _last_purchase_order_line(self):
        self.ensure_one()
        po_domain = [
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('purchase', 'done')),
            ('order_line.product_id', '=', self.product_id.id),
        ]
        request = self.request_id
        request_id = request.id if request and isinstance(request.id, int) else False
        if request_id:
            po_domain += [
                '|',
                ('zvy_purchase_request_id', '=', False),
                ('zvy_purchase_request_id', '!=', request_id),
            ]
        orders = self.env['purchase.order'].search(
            po_domain, order='date_approve desc, date_order desc, id desc', limit=20,
        )
        for order in orders:
            pol = order.order_line.filtered(
                lambda l: l.product_id == self.product_id
            )[:1]
            if pol:
                return pol
        return self.env['purchase.order.line']

    def _last_awarded_history_line(self):
        self.ensure_one()
        domain = [
            ('product_id', '=', self.product_id.id),
            ('company_id', '=', self.company_id.id),
            ('awarded_quote_id', '!=', False),
        ]
        if isinstance(self.id, int):
            domain.append(('id', '!=', self.id))
        request_id = self.request_id.id if self.request_id and isinstance(self.request_id.id, int) else False
        if request_id:
            domain.append(('request_id', '!=', request_id))
        return self.search(domain, order='id desc', limit=1)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            is_cm_or_admin = self._user_is_cm_or_admin()
            for vals in vals_list:
                request = self.env['zvy.purchase.request']
                if vals.get('request_id'):
                    request = request.browse(vals['request_id'])
                if not request:
                    continue
                if request.state in ('draft', 'correction'):
                    continue
                if request.state == 'signatory' and is_cm_or_admin:
                    continue
                raise UserError(_(
                    'Purchase request lines can only be added in Draft or '
                    'Correction, or by a Commercial Manager during Signatory.'
                ))
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('product_uom_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['product_uom_id'] = product.uom_id.id
        records = super().create(vals_list)
        records.mapped('request_id')._zvy_reset_signatory_if_effective_change()
        return records

    def write(self, vals):
        if not self.env.su:
            is_cm = self.env.user.has_group(
                'zvy_tendering.group_zvy_commercial_manager'
            )
            is_admin = self.env.user.has_group(
                'zvy_tendering.group_zvy_tendering_admin'
            )
            is_cm_or_admin = is_cm or is_admin
            # Quotes carry their own state/assignment guard (zvy.quote._check_can_edit),
            # so collecting them must stay possible while the PR is in inquiry.
            # Awarded quote is set by CM/Admin during quote review (and signatory reset).
            content_keys = set(vals) - {
                'expert_user_ids', 'quote_ids', 'awarded_quote_id',
                'awarded_bid_line_id', 'ce_retender',
                'award_not_lowest_reason', 'purchase_state',
            }
            if 'purchase_state' in vals:
                raise UserError(_(
                    'Line purchase state is updated only when creating or '
                    'rejecting purchase orders.'
                ))
            if content_keys:
                locked = self.filtered(
                    lambda l: l.request_id.state not in ('draft', 'correction')
                )
                signatory_ok = (
                    is_cm_or_admin
                    and set(vals) <= (
                        _SIGNATORY_EFFECTIVE_LINE_KEYS
                        | {'expert_user_ids', 'quote_ids', 'award_not_lowest_reason'}
                    )
                    and all(l.request_id.state == 'signatory' for l in locked)
                )
                if locked and not signatory_ok:
                    raise UserError(_(
                        'Purchase request lines can only be edited in Draft or Correction.'
                    ))
            if 'awarded_quote_id' in vals:
                if not is_cm_or_admin:
                    raise UserError(_(
                        'Only Commercial Managers can select the awarded quote.'
                    ))
                not_review = self.filtered(
                    lambda l: l.request_id.state not in ('quote_review', 'signatory')
                )
                if not_review:
                    raise UserError(_(
                        'Awarded quotes can only be set during Quote Review '
                        'or Signatory.'
                    ))
            if 'award_not_lowest_reason' in vals:
                if not is_cm_or_admin:
                    raise UserError(_(
                        'Only Commercial Managers can set the not-lowest-price reason.'
                    ))
            if 'expert_user_ids' in vals:
                if not is_cm_or_admin:
                    raise UserError(_(
                        'Only Commercial Managers can assign experts to lines.'
                    ))
        if 'awarded_quote_id' in vals:
            self._prepare_awarded_quote_vals(vals)
        res = super().write(vals)
        if 'awarded_quote_id' in vals:
            self._check_awarded_quote()
        if set(vals) & _SIGNATORY_EFFECTIVE_LINE_KEYS:
            self.mapped('request_id')._zvy_reset_signatory_if_effective_change()
        return res

    def unlink(self):
        if not self.env.su:
            is_cm_or_admin = self._user_is_cm_or_admin()
            locked = self.filtered(
                lambda l: l.request_id.state not in ('draft', 'correction')
            )
            if locked:
                if not (
                    is_cm_or_admin
                    and all(l.request_id.state == 'signatory' for l in locked)
                ):
                    raise UserError(_(
                        'Purchase request lines can only be removed in Draft '
                        'or Correction, or by a Commercial Manager during Signatory.'
                    ))
        requests = self.mapped('request_id')
        res = super().unlink()
        requests._zvy_reset_signatory_if_effective_change()
        return res

    def _user_is_cm_or_admin(self):
        return (
            self.env.su
            or self.env.user.has_group('zvy_tendering.group_zvy_commercial_manager')
            or self.env.user.has_group('zvy_tendering.group_zvy_tendering_admin')
        )

    def _prepare_awarded_quote_vals(self, vals):
        """Require or clear award_not_lowest_reason when setting the winner."""
        quote = self.env['zvy.quote'].browse(vals.get('awarded_quote_id') or [])
        if not quote:
            vals['award_not_lowest_reason'] = False
            return
        for line in self:
            if quote.line_id != line:
                continue
            if line._quote_is_lowest_price(quote):
                vals['award_not_lowest_reason'] = False
                return
            reason = vals.get('award_not_lowest_reason')
            if reason is None:
                reason = line.award_not_lowest_reason
            if not (reason or '').strip():
                raise ValidationError(_(
                    'A reason is required when awarding a quote that is not '
                    'the lowest price on %s.'
                ) % line.product_id.display_name)
            return

    def _comparable_quotes(self):
        """Priced non-draft quotes on this line (includes rejected, so a later award still compares)."""
        self.ensure_one()
        return self.quote_ids.filtered(
            lambda q: q.state != 'draft' and q._is_priced()
        )

    def _quote_is_lowest_price(self, quote):
        self.ensure_one()
        comparable = self._comparable_quotes()
        if not comparable:
            return True
        return quote.price_unit <= min(comparable.mapped('price_unit'))

    def _check_awarded_quote(self):
        for line in self:
            quote = line.awarded_quote_id
            if not quote:
                continue
            if quote.line_id != line:
                raise ValidationError(_(
                    'Awarded quote must belong to the same purchase request line.'
                ))
            if quote.state not in ('submitted', 'accepted'):
                raise ValidationError(_(
                    'Awarded quote must be submitted or accepted.'
                ))
            if not quote._is_priced():
                raise ValidationError(_(
                    'An unpriced quote cannot be selected as awarded.'
                ))
            if (
                not line._quote_is_lowest_price(quote)
                and not (line.award_not_lowest_reason or '').strip()
            ):
                raise ValidationError(_(
                    'A reason is required when awarding a quote that is not '
                    'the lowest price on %s.'
                ) % line.product_id.display_name)

    def _live_quote_count(self):
        self.ensure_one()
        return len(self.quote_ids.filtered(lambda q: q.state != 'rejected'))

    def _valid_inquiry_count(self):
        """Priced, non-rejected quotes received within 30 days (FR-33)."""
        self.ensure_one()
        return len(self.quote_ids.filtered('is_valid_inquiry'))

    def _needs_quote_shortfall_reason(self):
        """True when 1–2 valid inquiries on a standard line and no justification yet."""
        self.ensure_one()
        if self.sole_source:
            return False
        count = self._valid_inquiry_count()
        if count < 1 or count >= 3:
            return False
        return not (self.quote_shortfall_reason or '').strip()

    def _check_quote_minima(self):
        """≥1 valid inquiry always; ≥3 on standard lines unless a shortfall reason is set (FR-10 / FR-33)."""
        for line in self:
            count = line._valid_inquiry_count()
            if count < 1:
                raise ValidationError(_(
                    'Line %(product)s requires at least 1 valid inquiry; found %(count)s.',
                    product=line.product_id.display_name,
                    count=count,
                ))
            if line.sole_source:
                continue
            if count < 3 and not (line.quote_shortfall_reason or '').strip():
                raise ValidationError(_(
                    'Line %(product)s has %(count)s valid inquiry(ies). '
                    'Record at least 3, or provide a reason for submitting fewer.',
                    product=line.product_id.display_name,
                    count=count,
                ))

    def action_view_quotes(self):
        """Open this line’s form (details + quotes), same view as My Assignments."""
        self.ensure_one()
        return {
            'name': _('Purchase Request Line'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.purchase.request.line',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('zvy_tendering.view_zvy_purchase_request_line_form').id, 'form')],
            'target': 'current',
        }

    def _action_open_quote_shortfall_wizard(self):
        return {
            'name': _('Fewer than 3 Valid Inquiries'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.quote.shortfall.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_line_ids': [(6, 0, self.ids)]},
        }

    def action_submit_quotes(self):
        """Assigned expert submits the quote set collected on these lines."""
        if not self:
            return True
        is_admin = self.env.user.has_group('zvy_tendering.group_zvy_tendering_admin')
        for line in self:
            if line.request_id.state != 'inquiry':
                raise UserError(_(
                    'Quotes can only be submitted while the purchase request '
                    'is in Inquiry.'
                ))
            if line.request_id.procurement_type != 'enquiry':
                raise UserError(_(
                    'Quotes can only be submitted on Enquiry purchase requests.'
                ))
            if line.quotes_submitted:
                raise UserError(_(
                    'Quotes for %s were already submitted.'
                ) % line.product_id.display_name)
            if not self.env.su and not is_admin:
                if self.env.user not in line.expert_user_ids:
                    raise UserError(_(
                        'Only the assigned Commercial Expert can submit quotes '
                        'for %s.'
                    ) % line.product_id.display_name)
        if self.env.context.get('zvy_ui_submit'):
            shortfall = self.filtered(lambda l: l._needs_quote_shortfall_reason())
            if shortfall:
                return shortfall._action_open_quote_shortfall_wizard()
        self._check_quote_minima()
        self.quote_ids.filtered(lambda q: q.state == 'draft').sudo().write({
            'state': 'submitted',
        })
        # Experts have no write access on the PR; aggregate as superuser.
        author = self.env.user.partner_id.id
        for request in self.sudo().mapped('request_id'):
            lines = self.sudo().filtered(lambda l: l.request_id == request)
            details = []
            for line in lines:
                name = line.product_id.display_name
                reason = (line.quote_shortfall_reason or '').strip()
                if reason and not line.sole_source and line._valid_inquiry_count() < 3:
                    details.append(_('%s (%s)') % (name, reason))
                else:
                    details.append(name)
            request.message_post(
                body=_('Quotes submitted for: %s') % ', '.join(details),
                author_id=author,
            )
            request._try_advance_to_quote_review()
        return True
