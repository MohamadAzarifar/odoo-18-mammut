# -*- coding: utf-8 -*-
from odoo import api, fields, models

from ..hooks import ensure_product_template_columns


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def _prepare_setup(self):
        # Columns must exist before setup_models flushes product.template
        # (UI install/upgrade on a ready registry, and restart without -u
        # after deploying new fields). Missing columns break any form that
        # prefetches product.product.display_name, including AVL.
        ensure_product_template_columns(self.env.cr)
        super()._prepare_setup()

    zvy_procurement_type = fields.Selection(
        selection=[
            ('enquiry', 'Enquiry'),
            ('tendering', 'Tendering'),
        ],
        string='Default Procurement Type',
        required=True,
        default='enquiry',
        help='Group default. Enquiry products follow the standard quote inquiry '
             'path. Tendering products follow the closed-envelope path. '
             'A purchase request may contain only one resolved type. '
             'Optional per-company overlays override this for that company.',
    )
    zvy_need_commission = fields.Boolean(
        string='Default Need Commission',
        default=False,
        help='Group default. When enabled on an Enquiry product, approved quotes '
             'route to the Holding Commission unless a holding overlay overrides '
             'this flag. Hidden and cleared for Tendering.',
    )
    zvy_procurement_company_ids = fields.One2many(
        'zvy.product.procurement.company',
        'product_tmpl_id',
        string='Company Procurement Overrides',
        help='Optional per-company procurement type. Need Commission overlay '
             'is only valid on the head holding and applies to all descendants.',
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

    def _zvy_resolve_procurement(self, company):
        """Return ``(procurement_type, need_commission)`` for this template and company."""
        self.ensure_one()
        return self._zvy_resolve_procurement_map(company)[self.id]

    def _zvy_resolve_procurement_map(self, company):
        """Map template id → ``(procurement_type, need_commission)`` for one company.

        Type overlay is keyed by the operating company. Need Commission overlay
        is keyed by the head holding (``root_id``). Resolve uses sudo so a
        subsidiary user still picks up a holding overlay.
        """
        result = {}
        if not company:
            for tmpl in self:
                ptype = tmpl.zvy_procurement_type or 'enquiry'
                result[tmpl.id] = (
                    ptype,
                    bool(ptype == 'enquiry' and tmpl.zvy_need_commission),
                )
            return result
        holding = company._zvy_holding_company()
        Overlay = self.env['zvy.product.procurement.company'].sudo()
        overlays = Overlay.search([
            ('product_tmpl_id', 'in', self.ids),
            ('company_id', 'in', list({company.id, holding.id})),
        ])
        by_key = {
            (overlay.product_tmpl_id.id, overlay.company_id.id): overlay
            for overlay in overlays
        }
        for tmpl in self:
            type_overlay = by_key.get((tmpl.id, company.id))
            ptype = (
                type_overlay.procurement_type
                if type_overlay and type_overlay.procurement_type
                else (tmpl.zvy_procurement_type or 'enquiry')
            )
            if ptype != 'enquiry':
                result[tmpl.id] = (ptype, False)
                continue
            hold_overlay = by_key.get((tmpl.id, holding.id))
            if hold_overlay and hold_overlay.override_need_commission:
                need = bool(hold_overlay.need_commission)
            else:
                need = bool(tmpl.zvy_need_commission)
            result[tmpl.id] = (ptype, need)
        return result


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _zvy_resolve_procurement(self, company):
        self.ensure_one()
        return self.product_tmpl_id._zvy_resolve_procurement(company)
