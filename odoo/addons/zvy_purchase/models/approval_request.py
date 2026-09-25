from odoo import _, fields, models


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    zvy_purchase_request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        string="Purchase Request",
        ondelete="set null",
        index=True,
        copy=False,
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
