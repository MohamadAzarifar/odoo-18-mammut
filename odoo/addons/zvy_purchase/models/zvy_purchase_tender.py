from odoo import _, api, fields, models


class ZvyPurchaseTender(models.Model):
    _name = "zvy.purchase.tender"
    _description = "Tender"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default="New", readonly=True)
    request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        string="Purchase Request",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="request_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    item_ids = fields.Many2many(
        comodel_name="zvy.purchase.item",
        relation="zvy_purchase_tender_item_rel",
        column1="tender_id",
        column2="item_id",
        string="Purchase Items",
        tracking=True,
    )
    item_count = fields.Integer(compute="_compute_item_count")

    @api.depends("item_ids")
    def _compute_item_count(self):
        for tender in self:
            tender.item_count = len(tender.item_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("zvy.purchase.tender")
                    or "New"
                )
        return super().create(vals_list)

    def action_open_purchase_request(self):
        self.ensure_one()
        company = self.request_id.company_id
        allowed = list(self.env.context.get("allowed_company_ids") or [])
        if company.id in allowed:
            allowed.remove(company.id)
        allowed.insert(0, company.id)
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Request"),
            "res_model": "zvy.purchase.request",
            "res_id": self.request_id.id,
            "view_mode": "form",
            "target": "current",
            "context": {"allowed_company_ids": allowed},
        }
