# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
        help='Forces a minimum of one quote and includes CEO in the signatory chain.',
    )
    is_commission_item = fields.Boolean(
        string='Commission Item',
        compute='_compute_is_commission_item',
        store=True,
        readonly=False,
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

    @api.depends('price_estimate', 'product_uom_qty')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_estimate

    @api.depends('quote_ids')
    def _compute_quote_count(self):
        for line in self:
            line.quote_count = len(line.quote_ids)

    @api.depends('product_id', 'product_id.categ_id.zvy_is_commission_item')
    def _compute_is_commission_item(self):
        for line in self:
            line.is_commission_item = bool(
                line.product_id.categ_id.zvy_is_commission_item
            )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            self.is_commission_item = bool(
                self.product_id.categ_id.zvy_is_commission_item
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('product_uom_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['product_uom_id'] = product.uom_id.id
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            # Quotes carry their own state/assignment guard (zvy.quote._check_can_edit),
            # so collecting them must stay possible while the PR is in inquiry.
            content_keys = set(vals) - {'expert_user_ids', 'quote_ids'}
            if content_keys:
                locked = self.filtered(
                    lambda l: l.request_id.state not in ('draft', 'correction')
                )
                if locked:
                    raise UserError(_(
                        'Purchase request lines can only be edited in Draft or Correction.'
                    ))
            if 'expert_user_ids' in vals:
                is_cm = self.env.user.has_group(
                    'zvy_tendering.group_zvy_commercial_manager'
                )
                is_admin = self.env.user.has_group(
                    'zvy_tendering.group_zvy_tendering_admin'
                )
                if not (is_cm or is_admin):
                    raise UserError(_(
                        'Only Commercial Managers can assign experts to lines.'
                    ))
        return super().write(vals)
