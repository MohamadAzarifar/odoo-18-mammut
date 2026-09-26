from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        user = request.env.user
        if not (
            user.has_group("zvy_purchase.group_commission_manager")
            or user.has_group("zvy_purchase.group_commission_expert")
        ):
            return result
        user_companies = result.get("user_companies")
        if not user_companies:
            return result

        all_companies = request.env["res.company"].sudo().search([])
        disallowed_ancestor_companies_sudo = all_companies.parent_ids - all_companies
        all_companies_in_hierarchy_sudo = disallowed_ancestor_companies_sudo + all_companies
        user_companies["allowed_companies"] = {
            company.id: {
                "id": company.id,
                "name": company.name,
                "sequence": company.sequence,
                "child_ids": (company.child_ids & all_companies_in_hierarchy_sudo).ids,
                "parent_id": company.parent_id.id,
            }
            for company in all_companies
        }
        user_companies["disallowed_ancestor_companies"] = {}
        result["display_switch_company_menu"] = len(all_companies) > 1
        return result
