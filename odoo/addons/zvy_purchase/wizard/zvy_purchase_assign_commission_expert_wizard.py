from odoo import _, fields, models
from odoo.exceptions import AccessError


class ZvyPurchaseAssignCommissionExpertWizard(models.TransientModel):
    _name = "zvy.purchase.assign.commission.expert.wizard"
    _description = "Assign Commission Experts"

    case_id = fields.Many2one(
        comodel_name="zvy.purchase.commission.case",
        string="Commission Case",
        required=True,
        readonly=True,
    )
    commission_expert_ids = fields.Many2many(
        comodel_name="res.users",
        relation="zvy_purchase_assign_commission_expert_wizard_rel",
        column1="wizard_id",
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
    )

    def action_assign(self):
        self.ensure_one()
        if not self.env.user.has_group("zvy_purchase.group_commission_manager"):
            raise AccessError(
                _("Only a Commission Manager can assign commission experts.")
            )
        self.case_id.write(
            {"commission_expert_ids": [(6, 0, self.commission_expert_ids.ids)]}
        )
        return {"type": "ir.actions.act_window_close"}
