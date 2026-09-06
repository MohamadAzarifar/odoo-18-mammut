# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .zvy_purchase_bands import ZVY_VALID_INQUIRY_DAYS


class ZvyQuote(models.Model):
    _name = 'zvy.quote'
    _description = 'Inquiry Quote'
    _order = 'id'

    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    line_id = fields.Many2one(
        'zvy.purchase.request.line',
        string='Request Line',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='request_id.company_id',
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(related='request_id.currency_id')
    request_state = fields.Selection(
        related='request_id.state',
        string='Request Status',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        ondelete='restrict',
        domain="[('id', 'in', allowed_partner_ids)]",
    )
    allowed_partner_ids = fields.Many2many(
        'res.partner',
        string='Allowed Vendors',
        compute='_compute_allowed_partner_ids',
        depends_context=('uid', 'company'),
        help='Active AVL vendors for this company and the line product/category.',
    )
    price_unit = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        required=True,
        default=0.0,
    )
    amount_total = fields.Monetary(
        string='Total',
        currency_field='currency_id',
        compute='_compute_amount_total',
        store=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'zvy_quote_ir_attachment_rel',
        'quote_id',
        'attachment_id',
        string='Attachments',
    )
    expert_user_id = fields.Many2one(
        'res.users',
        string='Recorded By',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
        ],
        default='draft',
        required=True,
        copy=False,
        readonly=True,
        index=True,
    )
    is_awarded = fields.Boolean(
        string='Awarded',
        compute='_compute_is_awarded',
        help='True when this quote is the awarded quote on its request line.',
    )
    received_date = fields.Datetime(
        string='Received Date',
        default=fields.Datetime.now,
        help='When this inquiry response was received. Validity is 30 days from this date.',
    )
    is_valid_inquiry = fields.Boolean(
        string='Valid Inquiry',
        compute='_compute_is_valid_inquiry',
        help='Priced, not rejected, and received less than 30 days ago (FR-33).',
    )

    @api.depends('partner_id', 'partner_id.name', 'price_unit', 'currency_id')
    def _compute_display_name(self):
        for quote in self:
            vendor = quote.partner_id.display_name or _('Unknown vendor')
            if quote.currency_id:
                price = quote.currency_id.format(quote.price_unit)
            else:
                price = str(quote.price_unit)
            quote.display_name = '%s (%s)' % (vendor, price)

    @api.depends('line_id.awarded_quote_id')
    def _compute_is_awarded(self):
        for quote in self:
            quote.is_awarded = bool(
                quote.line_id.awarded_quote_id
                and quote.line_id.awarded_quote_id == quote
            )

    @api.depends('state', 'price_unit', 'received_date', 'create_date')
    def _compute_is_valid_inquiry(self):
        cutoff = fields.Datetime.now() - timedelta(days=ZVY_VALID_INQUIRY_DAYS)
        for quote in self:
            received = quote.received_date or quote.create_date
            quote.is_valid_inquiry = bool(
                quote.state != 'rejected'
                and quote.price_unit > 0
                and received
                and received >= cutoff
            )

    @api.depends('price_unit', 'line_id.product_uom_qty')
    def _compute_amount_total(self):
        for quote in self:
            qty = quote.line_id.product_uom_qty or 0.0
            quote.amount_total = quote.price_unit * qty

    @api.depends(
        'line_id',
        'line_id.product_id',
        'line_id.company_id',
        'request_id.company_id',
    )
    def _compute_allowed_partner_ids(self):
        Partner = self.env['res.partner']
        for quote in self:
            quote.allowed_partner_ids = Partner.search(
                self._partner_domain_for_line(quote.line_id)
            )

    @api.onchange('line_id')
    def _onchange_line_id(self):
        if self.line_id:
            self.request_id = self.line_id.request_id
        if self.partner_id and self.partner_id not in self.allowed_partner_ids:
            self.partner_id = False

    @api.model
    def _partner_domain_for_line(self, line):
        if not line:
            return [('id', '=', False)]
        company = line.company_id or line.request_id.company_id
        if not company:
            return [('id', '=', False)]
        return self.env['zvy.avl.entry']._avl_partner_domain(
            company,
            product=line.product_id,
            categ=line.product_id.categ_id if line.product_id else None,
        )

    def _check_avl(self):
        for quote in self:
            allowed = self.env['res.partner'].search(
                self._partner_domain_for_line(quote.line_id)
            )
            if quote.partner_id not in allowed:
                raise ValidationError(_(
                    'Vendor %(vendor)s is not on the active AVL for this product/company.',
                    vendor=quote.partner_id.display_name,
                ))

    def _check_can_edit(self):
        if self.env.su:
            return
        is_cm = self.env.user.has_group('zvy_tendering.group_zvy_commercial_manager')
        is_admin = self.env.user.has_group('zvy_tendering.group_zvy_tendering_admin')
        for quote in self:
            if quote.request_id.state != 'inquiry':
                raise UserError(_(
                    'Quotes can only be edited while the purchase request is in Inquiry.'
                ))
            if quote.request_id.procurement_type != 'enquiry':
                raise UserError(_(
                    'Quotes can only be recorded on Enquiry purchase requests.'
                ))
            if is_cm or is_admin:
                continue
            if self.env.user not in quote.line_id.expert_user_ids:
                raise UserError(_(
                    'You can only edit quotes on lines assigned to you.'
                ))

    def _assert_system_fields_unchanged(self, vals):
        """Recorded By and State are set by defaults / workflow actions only."""
        if self.env.su:
            return
        forbidden = {'expert_user_id', 'state'} & set(vals)
        if forbidden:
            raise UserError(_(
                'Quote fields Recorded By and State are set by the system and '
                'cannot be edited manually.'
            ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('line_id') and not vals.get('request_id'):
                line = self.env['zvy.purchase.request.line'].browse(vals['line_id'])
                vals['request_id'] = line.request_id.id
            if not self.env.su:
                # Always attribute the quote to the user who creates it;
                # State always starts as draft (workflow actions advance it).
                vals['expert_user_id'] = self.env.user.id
                vals['state'] = 'draft'
        quotes = super().create(vals_list)
        quotes._check_can_edit()
        quotes._check_avl()
        return quotes

    def write(self, vals):
        self._assert_system_fields_unchanged(vals)
        # Workflow state transitions (submit / approve / reject) use sudo and
        # skip the inquiry edit guard — they only change state.
        content_keys = set(vals) - {'state'}
        if content_keys or not self.env.su:
            self._check_can_edit()
        res = super().write(vals)
        if {'partner_id', 'line_id', 'company_id'} & set(vals):
            self._check_avl()
        return res

    def unlink(self):
        self._check_can_edit()
        return super().unlink()

    def action_select_as_awarded(self):
        """CM selects this quote as the award; reject sibling quotes on the line."""
        self.ensure_one()
        if not self.env.su:
            is_cm = self.env.user.has_group(
                'zvy_tendering.group_zvy_commercial_manager'
            )
            is_admin = self.env.user.has_group(
                'zvy_tendering.group_zvy_tendering_admin'
            )
            if not (is_cm or is_admin):
                raise UserError(_(
                    'Only Commercial Managers can select the awarded quote.'
                ))
        if self.request_id.state != 'quote_review':
            raise UserError(_(
                'Awarded quotes can only be selected during Quote Review.'
            ))
        if self.state not in ('submitted', 'accepted', 'rejected'):
            raise UserError(_(
                'Only submitted quotes can be selected as awarded.'
            ))
        line = self.line_id.sudo()
        ctx_reason = (self.env.context.get('zvy_award_not_lowest_reason') or '').strip()
        if not line._quote_is_lowest_price(self):
            effective = ctx_reason or (line.award_not_lowest_reason or '').strip()
            if not effective:
                if self.env.context.get('zvy_ui_award'):
                    return self._action_open_award_not_lowest_wizard()
                raise ValidationError(_(
                    'A reason is required when awarding a quote that is not '
                    'the lowest price on %s.'
                ) % line.product_id.display_name)
        # Allow changing the winner: restore previously rejected quotes first.
        (line.quote_ids - self).filtered(
            lambda q: q.state == 'rejected'
        ).sudo().write({'state': 'submitted'})
        if self.state == 'rejected':
            self.sudo().write({'state': 'submitted'})
        siblings = (line.quote_ids - self).filtered(lambda q: q.state != 'draft')
        siblings.sudo().write({'state': 'rejected'})
        if self.state != 'submitted':
            self.sudo().write({'state': 'submitted'})
        line_vals = {'awarded_quote_id': self.id}
        if line._quote_is_lowest_price(self):
            line_vals['award_not_lowest_reason'] = False
        elif ctx_reason:
            line_vals['award_not_lowest_reason'] = ctx_reason
        line.write(line_vals)
        reason = (line.award_not_lowest_reason or '').strip()
        if reason:
            body = _(
                'Awarded quote selected for %(product)s: %(vendor)s.\n'
                'Reason (not lowest price): %(reason)s'
            ) % {
                'product': line.product_id.display_name,
                'vendor': self.partner_id.display_name,
                'reason': reason,
            }
        else:
            body = _('Awarded quote selected for %(product)s: %(vendor)s.') % {
                'product': line.product_id.display_name,
                'vendor': self.partner_id.display_name,
            }
        self.request_id.message_post(body=body)
        return True

    def _action_open_award_not_lowest_wizard(self):
        self.ensure_one()
        return {
            'name': _('Not the Lowest Price'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.award.not.lowest.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_quote_id': self.id},
        }
