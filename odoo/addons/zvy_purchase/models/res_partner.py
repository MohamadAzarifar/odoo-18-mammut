from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        product = self._zvy_avl_product_from_context()
        if product:
            for vals in vals_list:
                vals.setdefault("is_company", True)
                if "supplier_rank" in self._fields:
                    vals.setdefault("supplier_rank", 1)
        partners = super().create(vals_list)
        if product:
            Avl = self.env["zvy.purchase.avl"]
            for partner in partners:
                Avl._ensure(partner, product)
        return partners

    def _zvy_avl_product_from_context(self):
        product_id = self.env.context.get("zvy_avl_product_id")
        if not product_id:
            return self.env["product.product"]
        if isinstance(product_id, models.BaseModel):
            return product_id[:1]
        return self.env["product.product"].browse(int(product_id))
