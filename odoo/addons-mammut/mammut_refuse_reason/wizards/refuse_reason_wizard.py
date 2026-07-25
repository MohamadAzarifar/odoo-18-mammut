from odoo import api, fields, models, _
from markupsafe import Markup


class ApprovalRefuseReasonWizard(models.TransientModel):
    _name = "approval.refuse.reason.wizard"
    _description = "Approval Refuse Reason Wizard"

    request_id = fields.Many2one(
        "approval.request",
        string="Approval Request",
        required=True,
        readonly=True,
    )

    reason = fields.Text(
        string="Refuse Reason",
        required=True,
    )

    def action_submit_refuse_reason(self):
        self.ensure_one()

        approval = self.request_id

        # Call original refuse logic, but avoid opening wizard again
        super(approval.__class__, approval.with_context(skip_refuse_reason_wizard=True)).action_refuse()

        approval.message_post(
            body=Markup("<b>Refuse Reason:</b><br/>%s") % self.reason,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

        return {"type": "ir.actions.act_window_close"}
