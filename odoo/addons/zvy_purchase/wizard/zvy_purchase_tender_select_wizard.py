from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError


class ZvyPurchaseTenderSelectWizard(models.TransientModel):
    _name = "zvy.purchase.tender.select.wizard"
    _description = "Select Tender Offers"

    _EVALUATION_OFFER_STATES = frozenset(
        {"opened", "selected", "closed", "validated"}
    )

    tender_id = fields.Many2one(
        comodel_name="zvy.purchase.tender",
        string="Tender",
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name="zvy.purchase.tender.select.wizard.line",
        inverse_name="wizard_id",
        string="Offers",
    )

    def _zvy_offer_write(self):
        return self.env["zvy.purchase.offer"].sudo().with_context(
            zvy_skip_offer_edit_check=True
        )

    def _zvy_log_offer_change(self, offer, body):
        offer._message_log(body=body)
        if offer.item_id:
            offer.item_id._message_log(body=body)
        offer._zvy_log_on_request(body)

    def _zvy_effective_decision(self, offer_state):
        if offer_state == "validated":
            return "closed"
        return offer_state

    def _zvy_sync_item_states(self, items):
        """Selected if any Selected offer; otherwise Tendering while on a tender."""
        to_selected = self.env["zvy.purchase.item"]
        to_tendering = self.env["zvy.purchase.item"]
        for item in items:
            if item.state == "ordered":
                continue
            has_selected = any(
                offer.state == "selected" for offer in item.offer_ids
            )
            if has_selected and item.state != "selected":
                to_selected |= item
            elif not has_selected and item.state != "tendering":
                to_tendering |= item
        if to_selected:
            to_selected.with_context(
                zvy_skip_item_state_sync=True,
                zvy_skip_item_edit_check=True,
            ).sudo().write({"state": "selected"})
        if to_tendering:
            to_tendering.with_context(
                zvy_skip_item_state_sync=True,
                zvy_skip_item_edit_check=True,
            ).sudo().write({"state": "tendering"})

    def action_confirm(self):
        self.ensure_one()
        tender = self.tender_id
        tender._zvy_check_can_select()
        if tender.state != "evaluation":
            raise UserError(
                _("Offers can only be selected when the tender is Evaluation.")
            )

        lines_by_item = defaultdict(list)
        for line in self.line_ids:
            offer = line.offer_id
            if offer.state not in self._EVALUATION_OFFER_STATES:
                raise UserError(
                    _(
                        "Offer %(offer)s is not available for tender selection.",
                        offer=offer.display_name,
                    )
                )
            current = self._zvy_effective_decision(offer.state)
            if (
                line.decision in ("selected", "closed")
                and line.decision != current
                and not (line.description or "").strip()
            ):
                raise UserError(
                    _(
                        "A description is required when changing an offer "
                        "to Selected or Closed."
                    )
                )
            lines_by_item[offer.item_id].append(line)

        for item, lines in lines_by_item.items():
            selected_lines = [line for line in lines if line.decision == "selected"]
            if len(selected_lines) > 1:
                raise UserError(
                    _(
                        "Only one offer can be Selected per purchase item "
                        "(%(item)s).",
                        item=item.display_name,
                    )
                )

        Offer = self._zvy_offer_write()
        touched_items = self.env["zvy.purchase.item"]

        for item, lines in lines_by_item.items():
            touched_items |= item
            selected_line = next(
                (line for line in lines if line.decision == "selected"),
                None,
            )
            target_by_offer = {line.offer_id.id: line.decision for line in lines}
            if selected_line:
                for line in lines:
                    if line.id != selected_line.id:
                        target_by_offer[line.offer_id.id] = "closed"

            line_by_offer = {line.offer_id.id: line for line in lines}
            ordered_targets = sorted(
                target_by_offer.items(),
                key=lambda pair: {"closed": 0, "opened": 1, "selected": 2}[pair[1]],
            )
            for offer_id, target in ordered_targets:
                offer = Offer.browse(offer_id)
                if offer.state == target:
                    continue
                line = line_by_offer[offer_id]
                reason = (line.description or "").strip()
                offer.write({"state": target})
                if target == "selected":
                    body = _("Offer selected. Reason: %s") % reason
                elif target == "closed":
                    if reason:
                        body = _("Offer closed. Reason: %s") % reason
                    elif selected_line and offer_id != selected_line.offer_id.id:
                        body = _(
                            "Offer closed after selection of %(offer)s.",
                            offer=selected_line.offer_id.display_name,
                        )
                    else:
                        body = _("Offer closed after tender Select.")
                else:
                    body = _("Offer set to Opened.")
                self._zvy_log_offer_change(offer, body)

        # Any Validated offer not listed (should not happen) still closes.
        leftover_validated = tender.item_ids.offer_ids.filtered(
            lambda offer: offer.state == "validated"
        )
        if leftover_validated:
            Offer.browse(leftover_validated.ids).write({"state": "closed"})
            for offer in leftover_validated:
                self._zvy_log_offer_change(
                    offer,
                    _("Offer closed after tender Select."),
                )
                touched_items |= offer.item_id

        self._zvy_sync_item_states(tender.item_ids | touched_items)
        return {"type": "ir.actions.act_window_close"}


class ZvyPurchaseTenderSelectWizardLine(models.TransientModel):
    _name = "zvy.purchase.tender.select.wizard.line"
    _description = "Select Tender Offers Line"

    wizard_id = fields.Many2one(
        comodel_name="zvy.purchase.tender.select.wizard",
        required=True,
        ondelete="cascade",
    )
    offer_id = fields.Many2one(
        comodel_name="zvy.purchase.offer",
        string="Offer",
        required=True,
        readonly=True,
    )
    item_id = fields.Many2one(
        related="offer_id.item_id",
        string="Purchase Item",
        readonly=True,
    )
    vendor_id = fields.Many2one(
        related="offer_id.vendor_id",
        string="Vendor",
        readonly=True,
    )
    final_price = fields.Monetary(
        related="offer_id.final_price",
        string="Final Price",
        readonly=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="offer_id.currency_id",
        readonly=True,
    )
    decision = fields.Selection(
        selection=[
            ("opened", "Opened"),
            ("selected", "Selected"),
            ("closed", "Closed"),
        ],
        string="Decision",
        default="opened",
        required=True,
    )
    description = fields.Text(
        string="Description",
    )
