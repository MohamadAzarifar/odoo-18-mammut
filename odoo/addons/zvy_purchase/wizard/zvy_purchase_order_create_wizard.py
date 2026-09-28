from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseOrderCreateWizard(models.TransientModel):
    _name = "zvy.purchase.order.create.wizard"
    _description = "Create Purchase Order"

    request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        string="Purchase Request",
        required=True,
        readonly=True,
    )
    available_item_ids = fields.Many2many(
        comodel_name="zvy.purchase.item",
        relation="zvy_purchase_order_create_wizard_available_rel",
        column1="wizard_id",
        column2="item_id",
        string="Available Items",
        readonly=True,
    )
    item_ids = fields.Many2many(
        comodel_name="zvy.purchase.item",
        relation="zvy_purchase_order_create_wizard_item_rel",
        column1="wizard_id",
        column2="item_id",
        string="Purchase Items",
        domain="[('id', 'in', available_item_ids)]",
    )

    @api.model
    def _action_open(self, request):
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can create a purchase order.")
            )
        request.ensure_one()
        eligible = request._purchase_order_eligible_items()
        if not eligible:
            raise UserError(
                _(
                    "There are no purchase items ready for a purchase order "
                    "(Tendering with Selected offer + Approved approval, or "
                    "items on an Approved commission case with a Selected "
                    "offer, and not already on a purchase order)."
                )
            )
        wizard = self.create(
            {
                "request_id": request.id,
                "available_item_ids": [(6, 0, eligible.ids)],
                "item_ids": [(6, 0, eligible.ids)],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Purchase Order"),
            "res_model": "zvy.purchase.order.create.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can create a purchase order.")
            )
        eligible = self.request_id._purchase_order_eligible_items()
        items = self.item_ids & eligible
        if not items:
            raise UserError(
                _(
                    "Select at least one purchase item that is either "
                    "Tendering with a Selected offer and Approved approval, "
                    "or on an Approved commission case with a Selected "
                    "offer, and is not already on a purchase order."
                )
            )
        order = self.env["zvy.purchase.order"].create(
            {
                "request_id": self.request_id.id,
                "item_ids": [(6, 0, items.ids)],
            }
        )
        items.with_context(
            zvy_skip_item_state_sync=True,
            zvy_skip_item_edit_check=True,
        ).write({"state": "ordered"})
        self.request_id._message_log(
            body=_(
                "Purchase order created: %(name)s (%(items)s)",
                name=order.name,
                items=", ".join(items.mapped("name")),
            )
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "zvy.purchase.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }
