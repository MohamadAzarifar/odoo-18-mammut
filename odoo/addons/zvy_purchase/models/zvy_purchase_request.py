from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseMailMixin(models.AbstractModel):
    _name = "zvy.purchase.mail.mixin"
    _description = "Purchase chatter helpers"

    def _zvy_mail_request(self):
        return self.env["zvy.purchase.request"]

    def _zvy_log_on_request(self, body):
        for record in self:
            request = record._zvy_mail_request()
            if request:
                request._message_log(body=body)

    def _zvy_format_track_value(self, field, value):
        if field.type in ("many2one", "many2many", "one2many"):
            return ", ".join(value.mapped("display_name")) if value else "-"
        if field.type == "selection":
            return dict(field._description_selection(self.env)).get(value, value or "-")
        return value if value or value is False or value == 0 else "-"

    def _message_track(self, fields_iter, initial_values_dict):
        tracking = super()._message_track(fields_iter, initial_values_dict)
        if self.env.context.get("zvy_skip_parent_log"):
            return tracking
        for record in self:
            changes, _tracking_value_ids = tracking.get(record.id, (None, None))
            if not changes:
                continue
            request = record._zvy_mail_request()
            if not request or request == record:
                continue
            parts = []
            initial = initial_values_dict.get(record.id) or {}
            for fname in changes:
                field = record._fields[fname]
                old = record._zvy_format_track_value(field, initial.get(fname))
                new = record._zvy_format_track_value(field, record[fname])
                parts.append(f"{field.string}: {old} → {new}")
            body = _(
                "%(record)s: %(changes)s",
                record=record.display_name,
                changes="; ".join(parts),
            )
            request.with_context(zvy_skip_parent_log=True)._message_log(body=body)
            item = record.item_id if "item_id" in record._fields else False
            if item:
                item.with_context(zvy_skip_parent_log=True)._message_log(body=body)
        return tracking


class ZvyPurchaseRequest(models.Model):
    _name = "zvy.purchase.request"
    _description = "Purchase Request"
    _inherit = ["zvy.purchase.mail.mixin", "mail.thread"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default="New", readonly=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
        index=True,
        copy=False,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("in_review", "In Review"),
        ],
        default="draft",
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    item_ids = fields.One2many(
        comodel_name="zvy.purchase.item",
        inverse_name="request_id",
        string="Purchase Items",
    )
    can_edit_items = fields.Boolean(
        compute="_compute_can_edit_items",
    )

    @api.depends("state", "create_uid")
    @api.depends_context("uid")
    def _compute_can_edit_items(self):
        is_editor = self.env.user.has_group(
            "zvy_purchase.group_planner"
        ) or self.env.user.has_group("zvy_purchase.group_commercial_manager")
        for request in self:
            request.can_edit_items = bool(
                is_editor
                and request.state == "draft"
                and (
                    not request.create_uid
                    or request.create_uid == self.env.user
                    or not request.id
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Always the creator's active company; field is readonly afterward.
            vals["company_id"] = self.env.company.id
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("zvy.purchase.request")
                    or "New"
                )
        records = super().create(vals_list)
        for request in records:
            request._message_log(body=_("Purchase Request created."))
        return records

    def write(self, vals):
        if "company_id" in vals and not self.env.su:
            vals = dict(vals)
            vals.pop("company_id")
        return super().write(vals)

    def action_send(self):
        for request in self:
            if request.state != "draft":
                raise UserError(
                    _("Only draft purchase requests can be sent for review.")
                )
            if request.create_uid and request.create_uid != self.env.user:
                raise AccessError(
                    _("Only the creator of the purchase request can send it for review.")
                )
        self.write({"state": "in_review"})
        items = self.item_ids.with_context(zvy_skip_item_edit_check=True)
        if items:
            items.write({"state": "submitted"})
            items._zvy_mark_in_review_if_assigned()
        return True

    def action_back_to_draft(self):
        self.ensure_one()
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can send a purchase request back to draft.")
            )
        if self.state != "in_review":
            raise UserError(
                _("Only purchase requests in review can be sent back to draft.")
            )
        wizard = self.env["zvy.purchase.back.to.draft.wizard"].create(
            {"request_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Back to Draft"),
            "res_model": "zvy.purchase.back.to.draft.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_assign_expert(self):
        self.ensure_one()
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can assign commercial experts.")
            )
        if self.state != "in_review":
            raise UserError(
                _(
                    "Assign Expert is only available when the purchase request "
                    "is in review."
                )
            )
        wizard = self.env["zvy.purchase.assign.expert.wizard"].create(
            {
                "request_id": self.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "item_id": item.id,
                            "commercial_expert_ids": [
                                (6, 0, item.commercial_expert_ids.ids)
                            ],
                        },
                    )
                    for item in self.item_ids
                ],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Assign Expert"),
            "res_model": "zvy.purchase.assign.expert.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def unlink(self):
        self.item_ids.with_context(zvy_skip_item_edit_check=True).unlink()
        return super().unlink()

    def _zvy_mail_request(self):
        self.ensure_one()
        return self


class ZvyPurchaseItem(models.Model):
    _name = "zvy.purchase.item"
    _description = "Purchase Item"
    _inherit = ["zvy.purchase.mail.mixin", "mail.thread"]
    _order = "sequence_number, id"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, default="New", readonly=True)
    sequence_number = fields.Integer(copy=False)
    request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        store=True,
        index=True,
    )
    request_state = fields.Selection(
        related="request_id.state",
        string="Request Status",
        store=True,
    )
    request_name = fields.Char(
        related="request_id.name",
        string="Purchase Request",
        store=True,
    )
    request_create_uid = fields.Many2one(
        related="request_id.create_uid",
        store=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("in_review", "In Review"),
        ],
        default="draft",
        required=True,
        copy=False,
        index=True,
        tracking=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    product_qty = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
        required=True,
        default=1.0,
        tracking=True,
    )
    product_uom_category_id = fields.Many2one(
        related="product_id.uom_id.category_id",
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        required=True,
        ondelete="restrict",
        domain="[('category_id', '=', product_uom_category_id)]",
        tracking=True,
        default=lambda self: self.env.ref(
            "uom.product_uom_unit", raise_if_not_found=False
        ),
    )
    purchase_type_display = fields.Selection(
        selection=[
            ("enquiry", "Enquiry"),
            ("enquiry_commission", "Enquiry / Commission"),
            ("tendering", "Tendering"),
        ],
        string="Purchase Type",
        compute="_compute_purchase_type_display",
    )
    commercial_expert_ids = fields.Many2many(
        comodel_name="res.users",
        relation="zvy_purchase_item_commercial_expert_rel",
        column1="item_id",
        column2="user_id",
        string="Commercial Experts",
        domain=lambda self: [
            ("share", "=", False),
            ("groups_id", "in", self.env.ref("zvy_purchase.group_commercial_expert").ids),
            ("company_ids", "in", self.env.company.ids),
        ],
        tracking=True,
    )
    offer_ids = fields.One2many(
        comodel_name="zvy.purchase.offer",
        inverse_name="item_id",
        string="Offers",
    )
    offer_count = fields.Integer(
        string="Offers",
        compute="_compute_offer_count",
    )
    can_edit = fields.Boolean(
        compute="_compute_can_edit",
    )
    can_assign_experts = fields.Boolean(
        compute="_compute_can_assign_experts",
    )
    can_add_offers = fields.Boolean(
        compute="_compute_can_add_offers",
    )

    @api.depends(
        "product_id",
        "product_id.zvy_purchase_type",
        "product_id.zvy_need_commission",
        "product_id.zvy_purchase_type_company_values",
        "product_id.zvy_need_commission_company_values",
    )
    @api.depends_context("company")
    def _compute_purchase_type_display(self):
        for item in self:
            product = item.product_id
            if not product:
                item.purchase_type_display = False
            elif product.zvy_purchase_type == "tendering":
                item.purchase_type_display = "tendering"
            elif product.zvy_need_commission:
                item.purchase_type_display = "enquiry_commission"
            else:
                item.purchase_type_display = "enquiry"

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = (
                self.product_id.uom_po_id or self.product_id.uom_id
            )
        else:
            self.product_uom_id = False

    @api.depends("offer_ids")
    def _compute_offer_count(self):
        for item in self:
            item.offer_count = len(item.offer_ids)

    @api.depends("request_state", "request_create_uid")
    @api.depends_context("uid")
    def _compute_can_edit(self):
        is_editor = self.env.user.has_group(
            "zvy_purchase.group_planner"
        ) or self.env.user.has_group("zvy_purchase.group_commercial_manager")
        for item in self:
            item.can_edit = bool(
                is_editor
                and item.request_state == "draft"
                and (
                    not item.request_create_uid
                    or item.request_create_uid == self.env.user
                )
            )

    @api.depends_context("uid")
    def _compute_can_assign_experts(self):
        is_cm = self.env.user.has_group("zvy_purchase.group_commercial_manager")
        for item in self:
            item.can_assign_experts = is_cm

    @api.depends("request_state", "state")
    @api.depends_context("uid")
    def _compute_can_add_offers(self):
        is_cm = self.env.user.has_group("zvy_purchase.group_commercial_manager")
        is_ce = self.env.user.has_group("zvy_purchase.group_commercial_expert")
        for item in self:
            if is_cm:
                item.can_add_offers = True
            elif is_ce:
                item.can_add_offers = (
                    item.request_state == "in_review" and item.state == "in_review"
                )
            else:
                item.can_add_offers = False

    def _zvy_check_can_add_offers(self):
        """Commercial Experts may add offers only when request and item are In Review."""
        if self.env.su:
            return
        is_cm = self.env.user.has_group("zvy_purchase.group_commercial_manager")
        is_ce = self.env.user.has_group("zvy_purchase.group_commercial_expert")
        if is_cm:
            return
        if not is_ce:
            raise AccessError(
                _(
                    "Only Commercial Experts and Commercial Managers can add "
                    "offers."
                )
            )
        for item in self:
            if item.request_state != "in_review" or item.state != "in_review":
                raise AccessError(
                    _(
                        "Commercial Experts can add offers only when both the "
                        "purchase request and the purchase item are in review."
                    )
                )

    def _zvy_check_can_assign_experts(self):
        if self.env.su:
            return
        if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
            raise AccessError(
                _("Only a Commercial Manager can assign commercial experts.")
            )

    def _zvy_mark_in_review_if_assigned(self):
        """Move items with commercial experts to In Review."""
        if self.env.context.get("zvy_skip_item_state_sync"):
            return
        to_review = self.filtered(
            lambda item: item.commercial_expert_ids and item.state != "in_review"
        )
        if to_review:
            to_review.with_context(
                zvy_skip_item_state_sync=True,
                zvy_skip_item_edit_check=True,
            ).write({"state": "in_review"})

    def _zvy_check_item_editable(self, requests=None):
        if self.env.su or self.env.context.get("zvy_skip_item_edit_check"):
            return
        requests = requests or self.mapped("request_id")
        for request in requests:
            if request.state != "draft":
                raise AccessError(
                    _(
                        "Purchase items can no longer be edited once the "
                        "request is in review."
                    )
                )
            if request.create_uid and request.create_uid != self.env.user:
                raise AccessError(
                    _(
                        "Only the creator of the purchase request can add or "
                        "edit its purchase items."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        Request = self.env["zvy.purchase.request"]
        Product = self.env["product.product"]
        requests = Request.browse(
            [vals["request_id"] for vals in vals_list if vals.get("request_id")]
        )
        self._zvy_check_item_editable(requests)
        if any(vals.get("commercial_expert_ids") for vals in vals_list):
            if not self.env.user.has_group("zvy_purchase.group_commercial_manager"):
                raise AccessError(
                    _("Only a Commercial Manager can assign commercial experts.")
                )
        for vals in vals_list:
            if vals.get("product_id") and not vals.get("product_uom_id"):
                product = Product.browse(vals["product_id"])
                vals["product_uom_id"] = (
                    product.uom_po_id or product.uom_id
                ).id
            vals.setdefault("state", "draft")
        records = super().create(vals_list)
        records._assign_sequence_names()
        records._zvy_mark_in_review_if_assigned()
        for record in records:
            body = _(
                "Purchase Item %(item)s created with product %(product)s "
                "(%(qty)s %(uom)s).",
                item=record.name,
                product=record.product_id.display_name,
                qty=record.product_qty,
                uom=record.product_uom_id.display_name,
            )
            record._message_log(body=body)
            record._zvy_log_on_request(body)
        return records

    def write(self, vals):
        sequence_only = set(vals) <= {"sequence_number", "name"}
        if self.env.context.get("mail_notrack") and sequence_only:
            return super().write(vals)

        expert_keys = {"commercial_expert_ids"}
        offer_keys = {"offer_ids"}
        state_keys = {"state"}
        keys = set(vals)

        if keys <= state_keys:
            return super().write(vals)

        if keys <= expert_keys:
            self._zvy_check_can_assign_experts()
            res = super().write(vals)
            self._zvy_mark_in_review_if_assigned()
            return res

        if keys <= offer_keys:
            return super().write(vals)

        if "commercial_expert_ids" in vals:
            self._zvy_check_can_assign_experts()
            other = {
                key: value
                for key, value in vals.items()
                if key != "commercial_expert_ids"
            }
            if other and other.keys() <= offer_keys:
                res = super().write(vals)
                self._zvy_mark_in_review_if_assigned()
                return res
            if other and other.keys() - state_keys:
                self._zvy_check_item_editable()
            res = super().write(vals)
            self._zvy_mark_in_review_if_assigned()
            return res

        self._zvy_check_item_editable()
        if vals.get("product_id") and "product_uom_id" not in vals:
            product = self.env["product.product"].browse(vals["product_id"])
            vals = dict(vals)
            vals["product_uom_id"] = (product.uom_po_id or product.uom_id).id
        return super().write(vals)

    def unlink(self):
        self._zvy_check_item_editable()
        self.offer_ids.sudo().unlink()
        for record in self:
            record._zvy_log_on_request(
                _("Purchase Item %s deleted.", record.name)
            )
        return super().unlink()

    def _zvy_mail_request(self):
        self.ensure_one()
        return self.request_id

    def _assign_sequence_names(self):
        for record in self:
            if record.name and record.name != "New":
                continue
            parent = record.request_id
            if not parent:
                continue
            siblings = self.search(
                [
                    ("request_id", "=", parent.id),
                    ("id", "!=", record.id),
                ]
            )
            number = max(siblings.mapped("sequence_number") or [0]) + 1
            record.with_context(mail_notrack=True).write(
                {
                    "sequence_number": number,
                    "name": f"{parent.name}-PI-{number}",
                }
            )


class ZvyPurchaseOffer(models.Model):
    _name = "zvy.purchase.offer"
    _description = "Offer"
    _inherit = ["zvy.purchase.mail.mixin", "mail.thread"]
    _order = "sequence_number, id"

    name = fields.Char(required=True, copy=False, default="New", readonly=True)
    sequence_number = fields.Integer(copy=False)
    item_id = fields.Many2one(
        comodel_name="zvy.purchase.item",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        related="item_id.product_id",
    )
    allowed_vendor_ids = fields.Many2many(
        comodel_name="res.partner",
        compute="_compute_allowed_vendor_ids",
    )
    vendor_id = fields.Many2one(
        comodel_name="res.partner",
        string="Vendor",
        required=True,
        ondelete="restrict",
        domain="['|', ('id', 'in', allowed_vendor_ids), ('id', '=', vendor_id)]",
        tracking=True,
        context={
            "default_is_company": True,
        },
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="item_id.company_id.currency_id",
    )
    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        tracking=True,
    )
    quantity = fields.Float(
        string="Quantity",
        digits="Product Unit of Measure",
        default=1.0,
        tracking=True,
    )
    total_price = fields.Monetary(
        string="Total Price",
        compute="_compute_prices",
        currency_field="currency_id",
    )
    payment_method = fields.Char(
        string="Payment Method",
        tracking=True,
        help="How payment is made (cash, cheque, credit, …).",
    )
    payment_duration = fields.Char(
        string="Payment Duration",
        tracking=True,
        help="Payment terms duration (e.g. 30 days, 60 days, …).",
    )
    deliver_time = fields.Date(
        string="Delivery Time",
        tracking=True,
    )
    discount_percent_per_unit = fields.Float(
        string="Discount % / Unit",
        digits=(16, 4),
        tracking=True,
        help="Discount rate per unit as a decimal fraction "
        "(e.g. 0.1 for 10%).",
    )
    final_price = fields.Monetary(
        string="Final Price",
        compute="_compute_prices",
        currency_field="currency_id",
    )
    can_edit = fields.Boolean(
        compute="_compute_can_edit",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        item_id = res.get("item_id") or self.env.context.get("default_item_id")
        if item_id and ("quantity" in fields_list or not fields_list):
            item = self.env["zvy.purchase.item"].browse(item_id)
            if item.exists():
                res["quantity"] = item.product_qty
        return res

    @api.depends("create_uid")
    @api.depends_context("uid")
    def _compute_can_edit(self):
        for offer in self:
            offer.can_edit = bool(
                not offer.create_uid or offer.create_uid == self.env.user
            )

    def _zvy_check_can_edit(self):
        """Only the offer creator may write or unlink the offer."""
        if self.env.su:
            return
        for offer in self:
            if offer.create_uid and offer.create_uid != self.env.user:
                raise AccessError(
                    _("Only the creator of an offer can modify or delete it.")
                )

    @api.onchange("item_id")
    def _onchange_item_id(self):
        if self.item_id:
            self.quantity = self.item_id.product_qty

    @api.depends("quantity", "unit_price", "discount_percent_per_unit")
    def _compute_prices(self):
        for offer in self:
            qty = offer.quantity or 0.0
            unit = offer.unit_price or 0.0
            discount = offer.discount_percent_per_unit or 0.0
            offer.total_price = qty * unit
            offer.final_price = unit * (1.0 - discount) * qty

    @api.model_create_multi
    def create(self, vals_list):
        Item = self.env["zvy.purchase.item"]
        if not self.env.su:
            items = Item.browse(
                [vals["item_id"] for vals in vals_list if vals.get("item_id")]
            )
            items._zvy_check_can_add_offers()
        for vals in vals_list:
            if vals.get("item_id") and "quantity" not in vals:
                item = Item.browse(vals["item_id"])
                vals["quantity"] = item.product_qty
        records = super().create(vals_list)
        records._ensure_vendor_avl()
        records._assign_sequence_names()
        for record in records:
            body = _(
                "Offer %(offer)s created with vendor %(vendor)s.",
                offer=record.name,
                vendor=record.vendor_id.display_name,
            )
            record._message_log(body=body)
            if record.item_id:
                record.item_id._message_log(body=body)
            record._zvy_log_on_request(body)
        return records

    def unlink(self):
        self._zvy_check_can_edit()
        for record in self:
            body = _("Offer %s deleted.", record.name)
            if record.item_id:
                record.item_id._message_log(body=body)
            record._zvy_log_on_request(body)
        return super().unlink()

    def write(self, vals):
        self._zvy_check_can_edit()
        res = super().write(vals)
        if "vendor_id" in vals or "item_id" in vals:
            self._ensure_vendor_avl()
        return res

    @api.depends("item_id.product_id", "vendor_id")
    def _compute_allowed_vendor_ids(self):
        Avl = self.env["zvy.purchase.avl"]
        for offer in self:
            product = offer.item_id.product_id
            offer.allowed_vendor_ids = (
                Avl.search([("product_id", "=", product.id)]).vendor_id
                if product
                else False
            )

    def _ensure_vendor_avl(self):
        Avl = self.env["zvy.purchase.avl"]
        for offer in self:
            if offer.vendor_id and offer.product_id:
                Avl._ensure(offer.vendor_id, offer.product_id)

    def _zvy_mail_request(self):
        self.ensure_one()
        return self.item_id.request_id

    def _assign_sequence_names(self):
        for record in self:
            if record.name and record.name != "New":
                continue
            parent = record.item_id
            if not parent:
                continue
            siblings = self.search(
                [
                    ("item_id", "=", parent.id),
                    ("id", "!=", record.id),
                ]
            )
            number = max(siblings.mapped("sequence_number") or [0]) + 1
            record.with_context(mail_notrack=True).write(
                {
                    "sequence_number": number,
                    "name": f"{parent.name}-OFR-{number}",
                }
            )
