from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseAssignTenderExpertWizard(models.TransientModel):
    _name = "zvy.purchase.assign.tender.expert.wizard"
    _description = "Assign"

    tender_id = fields.Many2one(
        comodel_name="zvy.purchase.tender",
        string="Tender",
        required=True,
        readonly=True,
    )
    commission_expert_id = fields.Many2one(
        comodel_name="res.users",
        string="Commission Expert",
        required=True,
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
                _("Only a Commission Manager can assign a commission expert.")
            )
        if self.tender_id.state != "in_review":
            raise UserError(
                _("A commission expert can only be assigned when the tender is In Review.")
            )
        self.tender_id.write(
            {
                "commission_expert_id": self.commission_expert_id.id,
                "state": "assigned",
            }
        )
        return {"type": "ir.actions.act_window_close"}
