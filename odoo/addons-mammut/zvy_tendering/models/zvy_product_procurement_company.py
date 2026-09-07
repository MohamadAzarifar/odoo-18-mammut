# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ZvyProductProcurementCompany(models.Model):
    _name = 'zvy.product.procurement.company'
    _description = 'Product Procurement Company Overlay'
    _order = 'product_tmpl_id, company_id'
    _rec_name = 'company_id'

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete='cascade',
    )
    procurement_type = fields.Selection(
        selection=[
            ('enquiry', 'Enquiry'),
            ('tendering', 'Tendering'),
        ],
        string='Procurement Type',
        help='Override the product default for this company. Leave empty to inherit.',
    )
    override_need_commission = fields.Boolean(
        string='Override Need Commission',
        help='When set, Need Commission for Enquiry PRs of this holding '
             '(and its subsidiaries) uses the value below instead of the product default. '
             'Only allowed on the head holding company.',
    )
    need_commission = fields.Boolean(
        string='Need Commission',
        help='Used when Override Need Commission is set and the resolved type is Enquiry.',
    )
    is_holding = fields.Boolean(
        string='Head Holding',
        compute='_compute_is_holding',
        help='True when this overlay company is the top of the company tree.',
    )

    _sql_constraints = [
        (
            'product_company_uniq',
            'unique(product_tmpl_id, company_id)',
            'A procurement overlay already exists for this product and company.',
        ),
    ]

    @api.depends('company_id', 'company_id.root_id')
    def _compute_is_holding(self):
        for overlay in self:
            company = overlay.company_id
            overlay.is_holding = bool(company) and company == company._zvy_holding_company()

    @api.depends('product_tmpl_id', 'company_id')
    def _compute_display_name(self):
        for overlay in self:
            product = overlay.product_tmpl_id.display_name or ''
            company = overlay.company_id.display_name or ''
            overlay.display_name = '%s @ %s' % (product, company) if product or company else ''

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id and self.company_id != self.company_id._zvy_holding_company():
            self.override_need_commission = False
            self.need_commission = False

    @api.onchange('override_need_commission')
    def _onchange_override_need_commission(self):
        if not self.override_need_commission:
            self.need_commission = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('override_need_commission'):
                vals['need_commission'] = False
        return super().create(vals_list)

    def write(self, vals):
        if 'override_need_commission' in vals and not vals.get('override_need_commission'):
            vals = dict(vals, need_commission=False)
        res = super().write(vals)
        extra = self.filtered(
            lambda overlay: not overlay.override_need_commission and overlay.need_commission
        )
        if extra:
            super(ZvyProductProcurementCompany, extra).write({'need_commission': False})
        return res

    @api.constrains(
        'product_tmpl_id',
        'company_id',
        'procurement_type',
        'override_need_commission',
    )
    def _check_has_override(self):
        for overlay in self:
            if not overlay.procurement_type and not overlay.override_need_commission:
                raise ValidationError(_(
                    'Set a procurement type override or enable Need Commission override.'
                ))

    @api.constrains('override_need_commission', 'company_id')
    def _check_holding_commission(self):
        for overlay in self:
            if not overlay.override_need_commission or not overlay.company_id:
                continue
            holding = overlay.company_id._zvy_holding_company()
            if overlay.company_id != holding:
                raise ValidationError(_(
                    'Need Commission overlay can only be set on the head holding company.'
                ))
