from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class ZvyPurchaseCommissionCase(models.Model):
    _name = "zvy.purchase.commission.case"
    _description = "Commission Case"
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
        relation="zvy_purchase_commission_case_item_rel",
        column1="case_id",
        column2="item_id",
        string="Purchase Items",
        tracking=True,
    )
    item_count = fields.Integer(compute="_compute_item_count")
    commission_expert_ids = fields.Many2many(
        comodel_name="res.users",
        relation="zvy_purchase_commission_case_expert_rel",
        column1="case_id",
        column2="user_id",
        string="Commission Experts",
        domain=lambda self: [
            ("share", "=", False),
            (
                "groups_id",
                "in",
                self.env.ref("zvy_purchase.group_commission_expert").ids,
            ),
        ],
        tracking=True,
    )
    can_assign_commission_experts = fields.Boolean(
        compute="_compute_can_assign_commission_experts",
    )

    @api.depends("item_ids")
    def _compute_item_count(self):
        for case in self:
            case.item_count = len(case.item_ids)

    @api.depends_context("uid")
    def _compute_can_assign_commission_experts(self):
        is_manager = self.env.user.has_group(
            "zvy_purchase.group_commission_manager"
        )
        for case in self:
            case.can_assign_commission_experts = is_manager

    def _zvy_check_can_assign_commission_experts(self):
        if self.env.su:
            return
        if not self.env.user.has_group("zvy_purchase.group_commission_manager"):
            raise AccessError(
                _("Only a Commission Manager can assign commission experts.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "zvy.purchase.commission.case"
                    )
                    or "New"
                )
            if "commission_expert_ids" in vals:
                self._zvy_check_can_assign_commission_experts()
        return super().create(vals_list)

    def write(self, vals):
        if "commission_expert_ids" in vals:
            self._zvy_check_can_assign_commission_experts()
        return super().write(vals)

    def action_assign_commission_experts(self):
        self.ensure_one()
        self._zvy_check_can_assign_commission_experts()
        wizard = self.env["zvy.purchase.assign.commission.expert.wizard"].create(
            {
                "case_id": self.id,
                "commission_expert_ids": [(6, 0, self.commission_expert_ids.ids)],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Assign Experts"),
            "res_model": "zvy.purchase.assign.commission.expert.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

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
