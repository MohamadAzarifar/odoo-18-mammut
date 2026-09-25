from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    _ZVY_PURCHASE_ATTR_FIELDS = (
        "zvy_purchase_type",
        "zvy_need_commission",
        "zvy_operational",
        "zvy_purchase_type_company_values",
        "zvy_need_commission_company_values",
        "zvy_operational_company_values",
    )

    zvy_purchase_type_company_values = fields.Json(copy=False)
    zvy_need_commission_company_values = fields.Json(copy=False)
    zvy_operational_company_values = fields.Json(copy=False)
    zvy_purchase_type = fields.Selection(
        selection=[
            ("enquiry", "Enquiry"),
            ("tendering", "Tendering"),
        ],
        string="Purchase Type",
        compute="_compute_zvy_purchase_type",
        inverse="_inverse_zvy_purchase_type",
        store=False,
        default="enquiry",
    )
    zvy_need_commission = fields.Boolean(
        string="Need Commission?",
        compute="_compute_zvy_need_commission",
        inverse="_inverse_zvy_need_commission",
        store=False,
        default=False,
    )
    zvy_operational = fields.Boolean(
        string="Operational",
        compute="_compute_zvy_operational",
        inverse="_inverse_zvy_operational",
        store=False,
        default=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._zvy_check_purchase_attr_vals(vals)
            if vals.get("zvy_purchase_type") == "tendering":
                vals["zvy_need_commission"] = False
        return super().create(vals_list)

    def write(self, vals):
        self._zvy_check_purchase_attr_vals(vals)
        if vals.get("zvy_purchase_type") == "tendering":
            vals["zvy_need_commission"] = False
        return super().write(vals)

    @api.depends("zvy_purchase_type_company_values")
    @api.depends_context("company")
    def _compute_zvy_purchase_type(self):
        for product in self:
            product.zvy_purchase_type = product._zvy_resolve_company_map(
                product.zvy_purchase_type_company_values,
                "enquiry",
            )

    @api.depends(
        "zvy_need_commission_company_values",
        "zvy_purchase_type",
        "zvy_purchase_type_company_values",
    )
    @api.depends_context("company")
    def _compute_zvy_need_commission(self):
        for product in self:
            if product.zvy_purchase_type == "tendering":
                product.zvy_need_commission = False
            else:
                product.zvy_need_commission = bool(
                    product._zvy_resolve_company_map(
                        product.zvy_need_commission_company_values,
                        False,
                    )
                )

    def _inverse_zvy_purchase_type(self):
        for product in self:
            product._zvy_store_company_override(
                "zvy_purchase_type_company_values",
                product.zvy_purchase_type or "enquiry",
                "enquiry",
            )
            if product.zvy_purchase_type == "tendering":
                product._zvy_store_company_override(
                    "zvy_need_commission_company_values",
                    False,
                    False,
                )

    def _inverse_zvy_need_commission(self):
        for product in self:
            value = (
                False
                if product.zvy_purchase_type == "tendering"
                else bool(product.zvy_need_commission)
            )
            product._zvy_store_company_override(
                "zvy_need_commission_company_values",
                value,
                False,
            )

    @api.depends("zvy_operational_company_values")
    @api.depends_context("company")
    def _compute_zvy_operational(self):
        for product in self:
            product.zvy_operational = bool(
                product._zvy_resolve_company_map(
                    product.zvy_operational_company_values,
                    False,
                )
            )

    def _inverse_zvy_operational(self):
        for product in self:
            product._zvy_store_company_override(
                "zvy_operational_company_values",
                bool(product.zvy_operational),
                False,
            )

    @api.onchange("zvy_purchase_type")
    def _onchange_zvy_purchase_type(self):
        if self.zvy_purchase_type == "tendering":
            self.zvy_need_commission = False

    @api.constrains("zvy_purchase_type", "zvy_need_commission")
    def _check_zvy_need_commission(self):
        for product in self:
            if product.zvy_purchase_type == "tendering" and product.zvy_need_commission:
                raise ValidationError(
                    _("Need Commission cannot be set when Purchase Type is Tendering.")
                )

    @api.model
    def _zvy_check_purchase_attr_vals(self, vals):
        if self.env.su or self.env.context.get("_zvy_purchase_attr_inverse"):
            return
        changed = [fname for fname in self._ZVY_PURCHASE_ATTR_FIELDS if fname in vals]
        if not changed:
            return
        if self.env.user.has_group("zvy_purchase.group_commission_manager"):
            return
        defaults = {
            "zvy_purchase_type": "enquiry",
            "zvy_need_commission": False,
            "zvy_operational": False,
        }
        json_fields = {
            "zvy_purchase_type_company_values",
            "zvy_need_commission_company_values",
            "zvy_operational_company_values",
        }
        for fname in changed:
            if fname in json_fields or defaults.get(fname) != vals[fname]:
                raise AccessError(
                    _(
                        "Only Commission Managers can change Purchase Type, "
                        "Need Commission, and Operational."
                    )
                )

    def _zvy_company_chain_ids(self):
        # Parent-company walk is for JSON key lookup only; users may lack
        # res.company read on holding/parent companies.
        company = self.env.company.sudo()
        chain = list(reversed(company.parent_ids.ids))
        if company.id not in chain:
            chain.insert(0, company.id)
        return chain

    def _zvy_resolve_company_map(self, values, default, skip_company_id=None):
        values = values or {}
        for company_id in self._zvy_company_chain_ids():
            if skip_company_id and company_id == skip_company_id:
                continue
            key = str(company_id)
            if key in values:
                return values[key]
        return default

    def _zvy_store_company_override(self, json_fname, value, default):
        self.ensure_one()
        company_id = self.env.company.id
        key = str(company_id)
        values = dict(self[json_fname] or {})
        inherited = self._zvy_resolve_company_map(
            values,
            default,
            skip_company_id=company_id,
        )
        if value == inherited:
            values.pop(key, None)
        else:
            values[key] = value
        self.with_context(_zvy_purchase_attr_inverse=True).write(
            {json_fname: values or False}
        )
