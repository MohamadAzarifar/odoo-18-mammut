from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    zvy_purchase_request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        string="Purchase Request",
        ondelete="set null",
        index=True,
        copy=False,
    )
    zvy_purchase_item_ids = fields.Many2many(
        comodel_name="zvy.purchase.item",
        relation="approval_request_zvy_purchase_item_rel",
        column1="approval_id",
        column2="item_id",
        string="Purchase Items",
        copy=False,
    )

    @api.constrains("zvy_purchase_item_ids", "request_status")
    def _check_zvy_purchase_item_overlap(self):
        for approval in self:
            if (
                approval.request_status == "refused"
                or not approval.zvy_purchase_item_ids
            ):
                continue
            overlap = self.sudo().search(
                [
                    ("id", "!=", approval.id),
                    ("request_status", "!=", "refused"),
                    (
                        "zvy_purchase_item_ids",
                        "in",
                        approval.zvy_purchase_item_ids.ids,
                    ),
                ],
                limit=1,
            )
            if not overlap:
                continue
            shared = approval.zvy_purchase_item_ids & overlap.zvy_purchase_item_ids
            raise ValidationError(
                _(
                    "Purchase items %(items)s are already on approval %(approval)s. "
                    "A purchase item can be submitted again only when that "
                    "approval is Refused.",
                    items=", ".join(shared.mapped("display_name")),
                    approval=overlap.display_name,
                )
            )

    def action_open_purchase_request(self):
        self.ensure_one()
        if not self.zvy_purchase_request_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Request"),
            "res_model": "zvy.purchase.request",
            "res_id": self.zvy_purchase_request_id.id,
            "view_mode": "form",
            "target": "current",
        }
