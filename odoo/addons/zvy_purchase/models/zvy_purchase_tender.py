from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ZvyPurchaseTender(models.Model):
    _name = "zvy.purchase.tender"
    _description = "Tender"
    _inherit = ["mail.thread"]
    _order = "id desc"
    _check_company_auto = True

    _CE_WRITABLE_FIELDS = frozenset({"end_date", "state"})

    name = fields.Char(required=True, copy=False, default="New", readonly=True)
    request_id = fields.Many2one(
        comodel_name="zvy.purchase.request",
        string="Purchase Request",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="request_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    item_ids = fields.Many2many(
        comodel_name="zvy.purchase.item",
        relation="zvy_purchase_tender_item_rel",
        column1="tender_id",
        column2="item_id",
        string="Purchase Items",
        tracking=True,
    )
    item_count = fields.Integer(compute="_compute_item_count")
    state = fields.Selection(
        selection=[
            ("in_review", "In Review"),
            ("assigned", "Assigned"),
            ("scheduled", "Scheduled"),
            ("published", "Published"),
            ("opened", "Opened"),
        ],
        string="Status",
        default="in_review",
        required=True,
        tracking=True,
        copy=False,
    )
    end_date = fields.Datetime(
        string="End Date",
        tracking=True,
        copy=False,
    )
    commission_expert_id = fields.Many2one(
        comodel_name="res.users",
        string="Commission Expert",
        tracking=True,
        domain=lambda self: [
            ("share", "=", False),
            (
                "groups_id",
                "in",
                self.env.ref("zvy_purchase.group_commission_expert").ids,
            ),
        ],
    )
    can_assign_commission_expert = fields.Boolean(
        compute="_compute_can_assign_commission_expert",
    )
    can_schedule = fields.Boolean(compute="_compute_can_schedule")
    can_publish = fields.Boolean(compute="_compute_can_publish")
    can_open = fields.Boolean(compute="_compute_can_open")

    @api.depends("item_ids")
    def _compute_item_count(self):
        for tender in self:
            tender.item_count = len(tender.item_ids)

    @api.depends("state")
    @api.depends_context("uid")
    def _compute_can_assign_commission_expert(self):
        is_manager = self.env.user.has_group(
            "zvy_purchase.group_commission_manager"
        )
        for tender in self:
            tender.can_assign_commission_expert = (
                is_manager and tender.state == "in_review"
            )

    @api.depends("state", "commission_expert_id")
    @api.depends_context("uid")
    def _compute_can_schedule(self):
        uid = self.env.uid
        for tender in self:
            tender.can_schedule = bool(
                tender.state == "assigned"
                and tender.commission_expert_id
                and tender.commission_expert_id.id == uid
            )

    @api.depends("state", "commission_expert_id", "end_date")
    @api.depends_context("uid")
    def _compute_can_publish(self):
        uid = self.env.uid
        for tender in self:
            tender.can_publish = bool(
                tender.state == "scheduled"
                and tender.end_date
                and tender.commission_expert_id
                and tender.commission_expert_id.id == uid
            )

    @api.depends("state")
    @api.depends_context("uid")
    def _compute_can_open(self):
        is_cm = self.env.user.has_group(
            "zvy_purchase.group_commission_manager"
        )
        for tender in self:
            tender.can_open = bool(is_cm and tender.state == "published")

    def _zvy_check_can_assign_commission_expert(self):
        if self.env.su:
            return
        if not self.env.user.has_group("zvy_purchase.group_commission_manager"):
            raise AccessError(
                _("Only a Commission Manager can assign a commission expert.")
            )

    def _zvy_check_can_open(self):
        if self.env.su:
            return
        if not self.env.user.has_group("zvy_purchase.group_commission_manager"):
            raise AccessError(
                _("Only a Commission Manager can open a tender.")
            )

    def _zvy_check_assigned_commission_expert(self):
        if self.env.su:
            return
        for tender in self:
            if tender.commission_expert_id != self.env.user:
                raise AccessError(
                    _(
                        "Only the assigned Commission Expert can schedule "
                        "or publish this tender."
                    )
                )

    def _zvy_check_commission_expert_write(self, vals):
        """Commission Experts may only write end_date / state (Schedule, Publish)."""
        if self.env.su:
            return
        is_ce = self.env.user.has_group("zvy_purchase.group_commission_expert")
        is_cm = self.env.user.has_group("zvy_purchase.group_commission_manager")
        if not is_ce or is_cm:
            return
        forbidden = set(vals) - self._CE_WRITABLE_FIELDS
        if forbidden:
            raise AccessError(
                _(
                    "Commission Experts can only update End Date and Status "
                    "on tenders."
                )
            )

    def _zvy_sync_item_tendering_state(self):
        self.mapped("item_ids")._zvy_mark_tendering_if_on_tender()

    @api.model
    def _zvy_portal_vendor_domain(self, partner=None):
        """Domain: published tenders with a Validated/Bid offer for this vendor."""
        partner = partner or self.env.user.partner_id
        commercial = partner.commercial_partner_id
        return [
            ("state", "=", "published"),
            (
                "item_ids.offer_ids",
                "any",
                [
                    ("state", "in", ("validated", "bid")),
                    ("vendor_id", "child_of", commercial.id),
                ],
            ),
        ]

    def _zvy_portal_vendor_offers(self, partner=None):
        """Validated/Bid offers on this tender's items for the portal vendor."""
        self.ensure_one()
        partner = partner or self.env.user.partner_id
        commercial = partner.commercial_partner_id
        return self.env["zvy.purchase.offer"].search(
            [
                ("item_id", "in", self.item_ids.ids),
                ("state", "in", ("validated", "bid")),
                ("vendor_id", "child_of", commercial.id),
            ]
        )

    def _zvy_portal_bidding_open(self):
        self.ensure_one()
        if self.state != "published" or not self.end_date:
            return False
        return fields.Datetime.now() <= self.end_date

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("zvy.purchase.tender")
                    or "New"
                )
            if "commission_expert_id" in vals and vals.get("commission_expert_id"):
                self._zvy_check_can_assign_commission_expert()
        tenders = super().create(vals_list)
        tenders._zvy_sync_item_tendering_state()
        return tenders

    def write(self, vals):
        if "commission_expert_id" in vals:
            self._zvy_check_can_assign_commission_expert()
        self._zvy_check_commission_expert_write(vals)
        res = super().write(vals)
        if "item_ids" in vals:
            self._zvy_sync_item_tendering_state()
        return res

    def action_assign_commission_expert(self):
        self.ensure_one()
        self._zvy_check_can_assign_commission_expert()
        if self.state != "in_review":
            raise UserError(
                _("A commission expert can only be assigned when the tender is In Review.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Assign"),
            "res_model": "zvy.purchase.assign.tender.expert.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_tender_id": self.id,
                "default_commission_expert_id": self.commission_expert_id.id,
            },
        }

    def action_schedule(self):
        self.ensure_one()
        self._zvy_check_assigned_commission_expert()
        if self.state != "assigned":
            raise UserError(
                _("A tender can only be scheduled when it is Assigned.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Schedule"),
            "res_model": "zvy.purchase.schedule.tender.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_tender_id": self.id,
                "default_end_date": self.end_date,
            },
        }

    def action_publish(self):
        self.ensure_one()
        self._zvy_check_assigned_commission_expert()
        if self.state != "scheduled":
            raise UserError(
                _("A tender can only be published when it is Scheduled.")
            )
        if not self.end_date:
            raise UserError(
                _("Set an End Date before publishing the tender.")
            )
        self.write({"state": "published"})
        return True

    def action_open(self):
        self.ensure_one()
        self._zvy_check_can_open()
        if self.state != "published":
            raise UserError(
                _("A tender can only be opened when it is Published.")
            )
        bid_offers = self.item_ids.offer_ids.filtered(lambda o: o.state == "bid")
        self.write({"state": "opened"})
        if bid_offers:
            # Commission Manager has read-only offer ACL; elevate only for this
            # authorized Bid → Opened transition.
            bid_offers.sudo().with_context(zvy_skip_offer_edit_check=True).write(
                {"state": "opened"}
            )
        return True

    def action_open_purchase_request(self):
        self.ensure_one()
        company = self.request_id.company_id
        allowed = list(self.env.context.get("allowed_company_ids") or [])
        if company.id in allowed:
            allowed.remove(company.id)
        allowed.insert(0, company.id)
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Request"),
            "res_model": "zvy.purchase.request",
            "res_id": self.request_id.id,
            "view_mode": "form",
            "target": "current",
            "context": {"allowed_company_ids": allowed},
        }
