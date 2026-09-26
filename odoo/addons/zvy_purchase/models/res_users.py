from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_company_ids(self):
        """Commission Managers/Experts work holding-wide across all companies."""
        self.ensure_one()
        if self.has_group("zvy_purchase.group_commission_manager") or self.has_group(
            "zvy_purchase.group_commission_expert"
        ):
            return self.env["res.company"].sudo().search([("active", "=", True)])._ids
        return super()._get_company_ids()
