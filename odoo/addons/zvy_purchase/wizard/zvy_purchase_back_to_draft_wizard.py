from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseBackToDraftWizard(models.TransientModel):
    _name = "zvy.purchase.back.to.draft.wizard"
    _description = "Back to Draft"

    request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Reason",
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can send a purchase request back to draft.")
            )
        if self.request_id.state != "in_review":
            raise UserError(
                _("Only purchase requests in review can be sent back to draft.")
            )
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("A reason is required to send the purchase request back to draft."))
        self.request_id.write({"state": "draft"})
        items = self.request_id.item_ids.with_context(zvy_skip_item_edit_check=True)
        if items:
            items.write({"state": "draft"})
            items._zvy_mark_tendering_if_on_tender()
        self.request_id._message_log(
            body=_("Sent back to draft. Reason: %s") % reason
        )
        return {"type": "ir.actions.act_window_close"}
