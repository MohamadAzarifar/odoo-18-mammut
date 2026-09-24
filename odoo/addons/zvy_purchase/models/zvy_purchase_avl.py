from odoo import api, fields, models


class ZvyPurchaseAvl(models.Model):
    _name = "zvy.purchase.avl"
    _description = "AVL"
    _order = "vendor_id, product_id"

    vendor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
        required=True,
        ondelete="restrict",
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        required=True,
        ondelete="restrict",
        index=True,
    )

    @api.depends("vendor_id", "product_id")
    def _compute_display_name(self):
        for record in self:
            vendor = record.vendor_id.display_name or ""
            product = record.product_id.display_name or ""
            record.display_name = (
                f"{vendor} — {product}" if vendor or product else self._description
            )

    @api.model
    def _ensure(self, vendor, product):
        vendor_id = vendor.id if isinstance(vendor, models.BaseModel) else vendor
        product_id = product.id if isinstance(product, models.BaseModel) else product
        if not vendor_id or not product_id:
            return self.browse()
        existing = self.search(
            [
                ("vendor_id", "=", vendor_id),
                ("product_id", "=", product_id),
            ],
            limit=1,
        )
        if existing:
            return existing
        return self.create(
            {
                "vendor_id": vendor_id,
                "product_id": product_id,
            }
        )

    _sql_constraints = [
        (
            "vendor_product_uniq",
            "unique(vendor_id, product_id)",
            "This vendor is already listed for this product.",
        ),
    ]
