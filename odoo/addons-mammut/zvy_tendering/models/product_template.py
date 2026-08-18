# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    zvy_procurement_type = fields.Selection(
        selection=[
            ('enquiry', 'Enquiry'),
            ('tendering', 'Tendering'),
        ],
        string='Procurement Type',
        required=True,
        default='enquiry',
        help='Enquiry products follow the standard quote inquiry path. '
             'Tendering products follow the closed-envelope path. '
             'A purchase request may contain only one type.',
    )
    zvy_need_commission = fields.Boolean(
        string='Need Commission',
        default=False,
        help='When enabled on an Enquiry product, approved quotes route '
             'to the Holding Commission. Hidden and cleared for Tendering.',
    )

    @api.onchange('zvy_procurement_type')
    def _onchange_zvy_procurement_type(self):
        if self.zvy_procurement_type != 'enquiry':
            self.zvy_need_commission = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('zvy_procurement_type', 'enquiry') != 'enquiry':
                vals['zvy_need_commission'] = False
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('zvy_procurement_type') and vals['zvy_procurement_type'] != 'enquiry':
            vals = dict(vals, zvy_need_commission=False)
        res = super().write(vals)
        extra = self.filtered(
            lambda tmpl: tmpl.zvy_procurement_type != 'enquiry' and tmpl.zvy_need_commission
        )
        if extra:
            super(ProductTemplate, extra).write({'zvy_need_commission': False})
        return res
