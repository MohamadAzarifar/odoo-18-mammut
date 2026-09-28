from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseCommissionCaseStatusWizard(models.TransientModel):
    _name = "zvy.purchase.commission.case.status.wizard"
    _description = "Commission Case Status Change"

    case_id = fields.Many2one(
        comodel_name="zvy.purchase.commission.case",
        required=True,
        readonly=True,
    )
    target_state = fields.Selection(
        selection=[
            ("rejected", "Reject"),
            ("approved", "Approve"),
            ("correction", "Correction"),
        ],
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Reason",
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("zvy_purchase.group_commission_manager"):
            raise AccessError(
                _("Only a Commission Manager can change the commission case status.")
            )
        case = self.case_id
        if case.state != "in_review":
            raise UserError(
                _("Only commission cases in In Review can change status.")
            )
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("A reason is required to change the status."))
        labels = dict(self._fields["target_state"].selection)
        label = labels.get(self.target_state, self.target_state)
        case.write({"state": self.target_state})
        body = _("Commission case set to %s. Reason: %s") % (label, reason)
        case._message_log(body=body)
        return {"type": "ir.actions.act_window_close"}
