from odoo import api, fields, models


SCALE_SELECTION = [
    ("minor", "Minor"),
    ("medium", "Medium"),
    ("major", "Major"),
]

TIER_SELECTION = [
    ("small", "Small"),
    ("medium", "Medium"),
    ("major", "Major"),
    ("grand", "Grand"),
]


class ZvyPurchaseScale(models.Model):
    _name = "zvy.purchase.scale"
    _description = "Purchase Scale"
    _order = "id"

    name = fields.Char(required=True, translate=True)
    scale = fields.Selection(
        selection=SCALE_SELECTION,
        string="Scale",
        required=True,
    )
    rule_ids = fields.One2many(
        comodel_name="zvy.purchase.scale.rule",
        inverse_name="scale_id",
        string="Purchase Rules",
    )
    operational_rule_ids = fields.One2many(
        comodel_name="zvy.purchase.scale.rule",
        inverse_name="scale_id",
        string="Operational Rules",
        domain=[("category", "=", "operational")],
    )
    non_operational_rule_ids = fields.One2many(
        comodel_name="zvy.purchase.scale.rule",
        inverse_name="scale_id",
        string="Non-Operational Rules",
        domain=[("category", "=", "non_operational")],
    )

    _sql_constraints = [
        (
            "scale_uniq",
            "unique(scale)",
            "Each company scale may only be configured once.",
        ),
    ]

    def _get_tier_for_amount(self, category, amount):
        """Return the scale rule tier for an amount in the given category."""
        self.ensure_one()
        rules = self.rule_ids.filtered(lambda rule: rule.category == category)
        if not rules:
            return False
        closed = rules.filtered(lambda rule: not rule.is_open_ended).sorted(
            "amount_max"
        )
        for rule in closed:
            if amount <= rule.amount_max:
                return rule.tier
        open_ended = rules.filtered("is_open_ended")[:1]
        if open_ended:
            return open_ended.tier
        return False

    def _get_rule(self, category, tier):
        """Return the scale rule for category + tier, or an empty recordset."""
        self.ensure_one()
        if not tier:
            return self.env["zvy.purchase.scale.rule"]
        return self.rule_ids.filtered(
            lambda rule: rule.category == category and rule.tier == tier
        )[:1]


class ZvyPurchaseScaleRule(models.Model):
    _name = "zvy.purchase.scale.rule"
    _description = "Purchase Scale Rule"
    _order = "category, sequence, id"

    scale_id = fields.Many2one(
        comodel_name="zvy.purchase.scale",
        required=True,
        ondelete="cascade",
        index=True,
    )
    category = fields.Selection(
        selection=[
            ("operational", "Operational"),
            ("non_operational", "Non-Operational"),
        ],
        required=True,
        index=True,
    )
    tier = fields.Selection(
        selection=TIER_SELECTION,
        string="Purchase Type",
        required=True,
    )
    sequence = fields.Integer(default=10)
    amount_max = fields.Monetary(
        string="Threshold",
        currency_field="currency_id",
        required=True,
    )
    is_open_ended = fields.Boolean(
        string="Open-Ended",
        help="When set, the threshold is above amount_max rather than up to it.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.ref("base.IRR", raise_if_not_found=False)
        or self.env.company.currency_id,
    )
    announcement = fields.Text(string="Announcement")
    approval_category_id = fields.Many2one(
        comodel_name="approval.category",
        string="Approver",
        ondelete="restrict",
        domain=lambda self: [("company_id", "in", self.env.companies.ids)],
    )
    advance_guarantee = fields.Text(string="Advance Payment Guarantee")
    performance_guarantee = fields.Text(string="Performance Guarantee")
    required_documents = fields.Text(string="Required Documents")

    _sql_constraints = [
        (
            "scale_category_tier_uniq",
            "unique(scale_id, category, tier)",
            "Each scale may only have one rule per category and purchase type.",
        ),
    ]

    @api.depends("scale_id", "category", "tier")
    def _compute_display_name(self):
        category_labels = dict(self._fields["category"].selection)
        tier_labels = dict(self._fields["tier"].selection)
        for record in self:
            parts = [
                record.scale_id.display_name or "",
                category_labels.get(record.category, ""),
                tier_labels.get(record.tier, ""),
            ]
            record.display_name = " / ".join(p for p in parts if p) or self._description
