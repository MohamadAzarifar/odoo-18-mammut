from odoo import api, fields, models

from .zvy_purchase_scale import SCALE_SELECTION


class ResCompany(models.Model):
    _inherit = "res.company"

    zvy_purchase_scale = fields.Selection(
        selection=SCALE_SELECTION,
        string="Scale",
        default="minor",
        required=True,
    )
    zvy_purchase_operational_rule_ids = fields.Many2many(
        comodel_name="zvy.purchase.scale.rule",
        compute="_compute_zvy_purchase_scale_rule_ids",
        string="Operational Purchase Rules",
    )
    zvy_purchase_non_operational_rule_ids = fields.Many2many(
        comodel_name="zvy.purchase.scale.rule",
        compute="_compute_zvy_purchase_scale_rule_ids",
        string="Non-Operational Purchase Rules",
    )

    @api.depends("zvy_purchase_scale")
    def _compute_zvy_purchase_scale_rule_ids(self):
        Scale = self.env["zvy.purchase.scale"]
        for company in self:
            scale = Scale.search(
                [("scale", "=", company.zvy_purchase_scale)],
                limit=1,
            )
            company.zvy_purchase_operational_rule_ids = scale.operational_rule_ids
            company.zvy_purchase_non_operational_rule_ids = (
                scale.non_operational_rule_ids
            )
