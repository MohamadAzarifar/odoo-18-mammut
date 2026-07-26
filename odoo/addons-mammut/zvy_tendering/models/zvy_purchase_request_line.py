# -*- coding: utf-8 -*-
from odoo import api, fields, models


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

    @api.depends('product_uom_qty', 'price_estimate')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_estimate

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
