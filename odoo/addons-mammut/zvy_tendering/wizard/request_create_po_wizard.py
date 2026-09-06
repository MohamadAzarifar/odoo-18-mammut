# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ZvyRequestCreatePoWizard(models.TransientModel):
    _name = 'zvy.request.create.po.wizard'
    _description = 'Create Purchase Order'

    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade',
    )
    line_ids = fields.One2many(
        'zvy.request.create.po.wizard.line',
        'wizard_id',
        string='Lines',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        request_id = res.get('request_id') or self.env.context.get(
            'default_request_id'
        )
        if request_id:
            res['request_id'] = request_id
            if 'line_ids' in fields_list:
                request = self.env['zvy.purchase.request'].browse(request_id)
                res['line_ids'] = [
                    (0, 0, {
                        'line_id': line.id,
                        'selected': True,
                    })
                    for line in request._pending_po_lines()
                ]
        return res

    def action_confirm(self):
        self.ensure_one()
        selected = self.line_ids.filtered('selected').mapped('line_id')
        if not selected:
            raise UserError(_(
                'Select at least one pending line to create a purchase order.'
            ))
        return self.request_id._create_purchase_orders(selected)


class ZvyRequestCreatePoWizardLine(models.TransientModel):
    _name = 'zvy.request.create.po.wizard.line'
    _description = 'Create Purchase Order Wizard Line'

    wizard_id = fields.Many2one(
        'zvy.request.create.po.wizard',
        required=True,
        ondelete='cascade',
    )
    line_id = fields.Many2one(
        'zvy.purchase.request.line',
        string='Request Line',
        required=True,
        ondelete='cascade',
    )
    selected = fields.Boolean(string='Include', default=True)
    product_id = fields.Many2one(
        related='line_id.product_id',
        string='Product',
    )
    product_uom_qty = fields.Float(related='line_id.product_uom_qty')
    product_uom_id = fields.Many2one(related='line_id.product_uom_id')
    currency_id = fields.Many2one(related='line_id.currency_id')
    awarded_partner_id = fields.Many2one(
        'res.partner',
        string='Awarded Vendor',
        compute='_compute_award_display',
    )
    price_unit = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        compute='_compute_award_display',
    )

    @api.depends(
        'line_id.awarded_partner_id',
        'line_id.awarded_quote_id.price_unit',
        'line_id.price_estimate',
        'wizard_id.request_id.award_partner_id',
    )
    def _compute_award_display(self):
        for wizard_line in self:
            line = wizard_line.line_id
            request = wizard_line.wizard_id.request_id
            wizard_line.awarded_partner_id = (
                line.awarded_partner_id or request.award_partner_id
            )
            if line.awarded_quote_id:
                wizard_line.price_unit = line.awarded_quote_id.price_unit
            else:
                wizard_line.price_unit = line.price_estimate or 0.0
