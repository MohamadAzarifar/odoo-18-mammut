# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.osv import expression


class ZvyAvlEntry(models.Model):
    _name = 'zvy.avl.entry'
    _description = 'Approved Vendor List Entry'
    _order = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        index=True,
        ondelete='restrict',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        ondelete='cascade',
    )
    categ_id = fields.Many2one(
        'product.category',
        string='Product Category',
        ondelete='cascade',
    )
    active = fields.Boolean(default=True)
    date_start = fields.Date(string='Valid From')
    date_end = fields.Date(string='Valid To')

    @api.depends('partner_id', 'partner_id.name', 'product_id', 'categ_id')
    def _compute_display_name(self):
        for entry in self:
            name = entry.partner_id.display_name or ''
            scope = entry.product_id.display_name or entry.categ_id.display_name
            if scope:
                name = f'{name} ({scope})'
            entry.display_name = name

    @api.model
    def _avl_partner_domain(self, product=None, categ=None):
        """Return a domain on res.partner for active AVL vendors.

        Without product/categ: all active AVL partners.
        With product/categ: unscoped entries plus matching product/category rows.
        """
        today = fields.Date.context_today(self)
        domain = [
            ('active', '=', True),
            '|', ('date_start', '=', False), ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today),
        ]
        if product or categ:
            if product and not hasattr(product, 'id'):
                product = self.env['product.product'].browse(product)
            if product and not categ:
                categ = product.categ_id
            if categ and not hasattr(categ, 'id'):
                categ = self.env['product.category'].browse(categ)
            scope_parts = [[('product_id', '=', False), ('categ_id', '=', False)]]
            if product:
                scope_parts.append([('product_id', '=', product.id)])
            if categ:
                scope_parts.append([('categ_id', '=', categ.id), ('product_id', '=', False)])
            domain = expression.AND([domain, expression.OR(scope_parts)])
        partner_ids = self.search(domain).mapped('partner_id').ids
        return [('id', 'in', partner_ids)]

    @api.model
    def _avl_partner_count(self, product=None, categ=None):
        """Distinct active AVL vendors for product/category scope."""
        domain = self._avl_partner_domain(product=product, categ=categ)
        if domain and domain[0][:2] == ('id', 'in'):
            return len(domain[0][2])
        return self.env['res.partner'].search_count(domain)

    @api.model
    def _trigger_pr_line_sole_source_recompute(self):
        """Refresh sole-source flags on draft/correction lines."""
        lines = self.env['zvy.purchase.request.line'].sudo().search([
            ('request_id.state', 'in', ('draft', 'correction')),
        ])
        if lines:
            lines._compute_sole_source()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._trigger_pr_line_sole_source_recompute()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(key in vals for key in (
            'active', 'partner_id', 'product_id', 'categ_id',
            'date_start', 'date_end',
        )):
            self._trigger_pr_line_sole_source_recompute()
        return res

    def unlink(self):
        res = super().unlink()
        self.env['zvy.avl.entry']._trigger_pr_line_sole_source_recompute()
        return res
