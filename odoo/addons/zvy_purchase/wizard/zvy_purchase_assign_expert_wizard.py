from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseAssignExpertWizard(models.TransientModel):
    _name = "zvy.purchase.assign.expert.wizard"
    _description = "Assign Commercial Experts"

    request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name="zvy.purchase.assign.expert.wizard.line",
        inverse_name="wizard_id",
        string="Purchase Items",
    )

    def action_assign(self):
        self.ensure_one()
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can assign commercial experts.")
            )
        if self.request_id.state != "in_review":
            raise UserError(
                _(
                    "Commercial experts can only be assigned from this wizard "
                    "when the purchase request is in review."
                )
            )
        for line in self.line_ids:
            line.item_id.write(
                {"commercial_expert_ids": [(6, 0, line.commercial_expert_ids.ids)]}
            )
        return {"type": "ir.actions.act_window_close"}


class ZvyPurchaseAssignExpertWizardLine(models.TransientModel):
    _name = "zvy.purchase.assign.expert.wizard.line"
    _description = "Assign Commercial Experts Line"

    wizard_id = fields.Many2one(
        comodel_name="zvy.purchase.assign.expert.wizard",
        required=True,
        ondelete="cascade",
    )
    item_id = fields.Many2one(
        comodel_name="zvy.purchase.item",
        required=True,
        readonly=True,
    )
    item_name = fields.Char(
        related="item_id.name",
        string="Purchase Item",
    )
    product_id = fields.Many2one(
        related="item_id.product_id",
        string="Product",
    )
    commercial_expert_ids = fields.Many2many(
        comodel_name="res.users",
        relation="zvy_purchase_assign_expert_wizard_line_rel",
        column1="line_id",
        column2="user_id",
        string="Commercial Experts",
        domain=lambda self: [
            ("share", "=", False),
            (
                "groups_id",
                "in",
                self.env.ref("zvy_purchase.group_commercial_expert").ids,
            ),
            ("company_ids", "in", self.env.company.ids),
        ],
    )
