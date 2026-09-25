from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseOfferRejectWizard(models.TransientModel):
    _name = "zvy.purchase.offer.reject.wizard"
    _description = "Reject Offer"

    offer_id = fields.Many2one(
        comodel_name="zvy.purchase.offer",
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
                _("Only a Commercial Manager can reject an offer.")
            )
        if self.offer_id.state != "in_review":
            raise UserError(_("Only offers in review can be rejected."))
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("A reason is required to reject the offer."))
        offer = self.offer_id.with_context(zvy_skip_offer_edit_check=True)
        offer.write({"state": "rejected"})
        body = _("Offer rejected. Reason: %s") % reason
        offer._message_log(body=body)
        if offer.item_id:
            offer.item_id._message_log(body=body)
        offer._zvy_log_on_request(body)
        return {"type": "ir.actions.act_window_close"}
