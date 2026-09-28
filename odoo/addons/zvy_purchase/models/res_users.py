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

    def _zvy_purchase_allowed_company_ids(self, preferred_company=None):
        """Company context for opening cross-company purchase records.

        Commission roles get every active company (preferred first). Other users
        keep the current selection, ensuring the preferred company is included.
        """
        self.ensure_one()
        if self.has_group("zvy_purchase.group_commission_manager") or self.has_group(
            "zvy_purchase.group_commission_expert"
        ):
            allowed = list(self._get_company_ids())
        else:
            allowed = list(self.env.context.get("allowed_company_ids") or self.company_ids.ids)
        if preferred_company:
            company_id = preferred_company.id
            if company_id in allowed:
                allowed.remove(company_id)
            allowed.insert(0, company_id)
        return allowed
