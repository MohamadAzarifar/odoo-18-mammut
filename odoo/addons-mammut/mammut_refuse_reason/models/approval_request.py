from odoo import models


class ApprovalRequest(models.Model):
    _inherit = "approval.request"

    def action_refuse(self):
        if self.env.context.get("skip_refuse_reason_wizard"):
            return super().action_refuse()

        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Refuse Reason",
            "res_model": "approval.refuse.reason.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_request_id": self.id,
            },
        }
