from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseOfferSelectWizard(models.TransientModel):
    _name = "zvy.purchase.offer.select.wizard"
    _description = "Select Offer"

    item_id = fields.Many2one(
        comodel_name="zvy.purchase.item",
        string="Purchase Item",
        readonly=True,
    )
    available_offer_ids = fields.Many2many(
        comodel_name="zvy.purchase.offer",
        compute="_compute_available_offer_ids",
        string="Validated Offers",
    )
    selected_offer_id = fields.Many2one(
        comodel_name="zvy.purchase.offer",
        string="Offer",
        domain="[('id', 'in', available_offer_ids)]",
    )

    @api.depends("item_id")
    def _compute_available_offer_ids(self):
        Offer = self.env["zvy.purchase.offer"]
        for wizard in self:
            domain = [("state", "=", "validated")]
            if wizard.item_id:
                domain.append(("item_id", "=", wizard.item_id.id))
            wizard.available_offer_ids = Offer.search(domain)

    @api.model
    def _action_open(self, item=None):
        """Open the Select Offer wizard. Optional item scopes the validated list."""
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can select an offer.")
            )
        vals = {}
        if item:
            item.ensure_one()
            item._zvy_check_can_select_offers()
            vals["item_id"] = item.id
        wizard = self.create(vals)
        if not wizard.available_offer_ids:
            raise UserError(_("There are no validated offers to select."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Select Offer"),
            "res_model": "zvy.purchase.offer.select.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can select an offer.")
            )
        offer = self.selected_offer_id
        if not offer:
            raise UserError(_("Please select exactly one offer."))
        if offer.state != "validated":
            raise UserError(_("Only validated offers can be selected."))
        if self.item_id and offer.item_id != self.item_id:
            raise UserError(
                _("The selected offer does not belong to this purchase item.")
            )
        offer.item_id._zvy_check_can_select_offers()
        if offer not in self.available_offer_ids:
            raise UserError(_("The selected offer is not available."))
        reason_wizard = self.env["zvy.purchase.offer.select.reason.wizard"].create(
            {"offer_id": offer.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Selection Reason"),
            "res_model": "zvy.purchase.offer.select.reason.wizard",
            "res_id": reason_wizard.id,
            "view_mode": "form",
            "target": "new",
        }
