# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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
        compute='_compute_is_commission_item',
        store=True,
        help='True when the product category is marked as a commission item.',
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
    awarded_quote_id = fields.Many2one(
        'zvy.quote',
        string='Awarded Quote',
        copy=False,
        domain="[('line_id', '=', id), ('state', 'in', ('submitted', 'accepted'))]",
        help='Winning quote selected by the Commercial Manager in quote review.',
    )
    awarded_partner_id = fields.Many2one(
        'res.partner',
        string='Awarded Vendor',
        related='awarded_quote_id.partner_id',
        store=True,
    )

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

    @api.depends('product_id', 'product_id.categ_id.zvy_is_commission_item')
    def _compute_is_commission_item(self):
        for line in self:
            line.is_commission_item = bool(
                line.product_id.categ_id.zvy_is_commission_item
            )

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

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('product_uom_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['product_uom_id'] = product.uom_id.id
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            is_cm = self.env.user.has_group(
                'zvy_tendering.group_zvy_commercial_manager'
            )
            is_admin = self.env.user.has_group(
                'zvy_tendering.group_zvy_tendering_admin'
            )
            # Quotes carry their own state/assignment guard (zvy.quote._check_can_edit),
            # so collecting them must stay possible while the PR is in inquiry.
            # Awarded quote is set by CM/Admin during quote review.
            content_keys = set(vals) - {
                'expert_user_ids', 'quote_ids', 'awarded_quote_id',
            }
            if content_keys:
                locked = self.filtered(
                    lambda l: l.request_id.state not in ('draft', 'correction')
                )
                if locked:
                    raise UserError(_(
                        'Purchase request lines can only be edited in Draft or Correction.'
                    ))
            if 'awarded_quote_id' in vals:
                if not (is_cm or is_admin):
                    raise UserError(_(
                        'Only Commercial Managers can select the awarded quote.'
                    ))
                not_review = self.filtered(
                    lambda l: l.request_id.state != 'quote_review'
                )
                if not_review:
                    raise UserError(_(
                        'Awarded quotes can only be set during Quote Review.'
                    ))
            if 'expert_user_ids' in vals:
                if not (is_cm or is_admin):
                    raise UserError(_(
                        'Only Commercial Managers can assign experts to lines.'
                    ))
        res = super().write(vals)
        if 'awarded_quote_id' in vals:
            self._check_awarded_quote()
        return res

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

    def _check_quote_minima(self):
        """≥3 quotes per standard line, ≥1 for sole source (FR-10 / BR-2)."""
        for line in self:
            count = len(line.quote_ids.filtered(lambda q: q.state != 'rejected'))
            required = 1 if line.sole_source else 3
            if count < required:
                raise ValidationError(_(
                    'Line %(product)s requires at least %(required)s quote(s); '
                    'found %(count)s.',
                    product=line.product_id.display_name,
                    required=required,
                    count=count,
                ))

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
        self._check_quote_minima()
        self.quote_ids.filtered(lambda q: q.state == 'draft').sudo().write({
            'state': 'submitted',
        })
        # Experts have no write access on the PR; aggregate as superuser.
        author = self.env.user.partner_id.id
        for request in self.sudo().mapped('request_id'):
            lines = self.sudo().filtered(lambda l: l.request_id == request)
            request.message_post(
                body=_('Quotes submitted for: %s') % ', '.join(
                    lines.mapped('product_id.display_name')
                ),
                author_id=author,
            )
            request._try_advance_to_quote_review()
        return True
