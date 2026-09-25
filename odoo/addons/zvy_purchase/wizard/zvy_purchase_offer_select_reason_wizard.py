from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseOfferSelectReasonWizard(models.TransientModel):
    _name = "zvy.purchase.offer.select.reason.wizard"
    _description = "Select Offer Reason"

    offer_id = fields.Many2one(
        comodel_name="zvy.purchase.offer",
        string="Offer",
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
                _("Only a Commercial Manager can select an offer.")
            )
        offer = self.offer_id
        if offer.state != "validated":
            raise UserError(_("Only validated offers can be selected."))
        offer.item_id._zvy_check_can_select_offers()
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("A reason is required to select the offer."))
        # Sibling offers on the same item become Closed; only this one is Selected.
        siblings = offer.item_id.offer_ids - offer
        if siblings:
            siblings.with_context(zvy_skip_offer_edit_check=True).write(
                {"state": "closed"}
            )
        offer.with_context(zvy_skip_offer_edit_check=True).write(
            {"state": "selected"}
        )
        body = _("Offer selected: %(offer)s. Reason: %(reason)s") % {
            "offer": offer.display_name,
            "reason": reason,
        }
        offer._message_log(body=body)
        if offer.item_id:
            offer.item_id._message_log(body=body)
            if siblings:
                closed_body = _(
                    "Offers closed after selection of %(offer)s: %(closed)s.",
                    offer=offer.display_name,
                    closed=", ".join(siblings.mapped("display_name")),
                )
                offer.item_id._message_log(body=closed_body)
                offer._zvy_log_on_request(closed_body)
        offer._zvy_log_on_request(body)
        return {"type": "ir.actions.act_window_close"}
