from datetime import timedelta

from odoo import _, api, fields, models
from odoo.tools.misc import format_date


CARD_ICONS = {
    "request_draft": "fa-file-text-o",
    "request_in_review": "fa-search",
    "request_approval": "fa-check-square-o",
    "request_commission": "fa-gavel",
    "offer_in_review": "fa-handshake-o",
    "offer_validated": "fa-thumbs-up",
    "item_assigned": "fa-tasks",
    "offer_my_draft": "fa-pencil",
    "offer_my_rejected": "fa-times-circle",
    "offer_my_in_review": "fa-hourglass-half",
    "case_in_review": "fa-users",
    "tender_in_review": "fa-bullhorn",
    "tender_published": "fa-globe",
    "tender_evaluation": "fa-balance-scale",
    "tender_my_assigned": "fa-user",
    "tender_my_scheduled": "fa-calendar",
    "case_my_in_review": "fa-user-circle",
}


class ZvyPurchaseDashboard(models.AbstractModel):
    _name = "zvy.purchase.dashboard"
    _description = "Purchase Dashboard"

    @api.model
    def _queue_line_series(self, res_model, domain, days=14):
        """Daily create_date counts for domain over the last ``days`` calendar days."""
        today = fields.Date.context_today(self)
        start = today - timedelta(days=days - 1)
        start_dt = fields.Datetime.to_datetime(start)
        grouped = self.env[res_model].read_group(
            domain + [("create_date", ">=", start_dt)],
            ["create_date"],
            ["create_date:day"],
            orderby="create_date:day",
            lazy=False,
        )
        by_day = {}
        for row in grouped:
            day_value = row.get("create_date:day")
            if not day_value:
                continue
            # read_group day label is a localized string; use range start when present
            day_date = row.get("__range", {}).get("create_date:day", {}).get("from")
            if day_date:
                day_key = fields.Date.to_date(day_date)
            else:
                try:
                    day_key = fields.Date.to_date(day_value)
                except (ValueError, TypeError):
                    continue
            by_day[day_key] = row.get("__count") or row.get("create_date_count") or 0

        labels = []
        values = []
        for offset in range(days):
            day = start + timedelta(days=offset)
            labels.append(format_date(self.env, day, date_format="MM-dd"))
            values.append(by_day.get(day, 0))
        return {"labels": labels, "values": values}

    @api.model
    def get_dashboard_cards(self):
        """Return role-based work-queue cards (counts, charts, domains for list actions)."""
        user = self.env.user
        uid = self.env.uid
        cards = []
        seen = set()

        def add_card(key, title, res_model, domain):
            if key in seen:
                return
            seen.add(key)
            Model = self.env[res_model]
            count = Model.search_count(domain)
            total = Model.search_count([])
            share = round(100.0 * count / total) if total else 0
            others = max(total - count, 0)
            cards.append(
                {
                    "key": key,
                    "title": title,
                    "icon": CARD_ICONS.get(key, "fa-circle-o"),
                    "count": count,
                    "total": total,
                    "share": share,
                    "res_model": res_model,
                    "domain": domain,
                    "doughnut": {
                        "labels": [_("This queue"), _("Other")],
                        "values": [count, others],
                    },
                    "line": self._queue_line_series(res_model, domain),
                }
            )

        if user.has_group("zvy_purchase.group_planner"):
            add_card(
                "request_draft",
                _("Draft Requests"),
                "zvy.purchase.request",
                [("state", "=", "draft")],
            )
            add_card(
                "request_in_review",
                _("Requests In Review"),
                "zvy.purchase.request",
                [("state", "=", "in_review")],
            )
            add_card(
                "request_approval",
                _("Requests Approval"),
                "zvy.purchase.request",
                [("state", "=", "approval")],
            )
            add_card(
                "request_commission",
                _("Requests Commission"),
                "zvy.purchase.request",
                [("state", "=", "commission")],
            )

        if user.has_group("zvy_purchase.group_commercial_manager"):
            add_card(
                "request_in_review",
                _("Requests In Review"),
                "zvy.purchase.request",
                [("state", "=", "in_review")],
            )
            add_card(
                "request_approval",
                _("Requests Approval"),
                "zvy.purchase.request",
                [("state", "=", "approval")],
            )
            add_card(
                "request_commission",
                _("Requests Commission"),
                "zvy.purchase.request",
                [("state", "=", "commission")],
            )
            add_card(
                "offer_in_review",
                _("Offers In Review"),
                "zvy.purchase.offer",
                [("state", "=", "in_review")],
            )
            add_card(
                "offer_validated",
                _("Offers Validated"),
                "zvy.purchase.offer",
                [("state", "=", "validated")],
            )

        if user.has_group("zvy_purchase.group_commercial_expert"):
            add_card(
                "item_assigned",
                _("Assigned Items"),
                "zvy.purchase.item",
                [("commercial_expert_ids", "in", uid)],
            )
            add_card(
                "offer_my_draft",
                _("My Draft Offers"),
                "zvy.purchase.offer",
                [("create_uid", "=", uid), ("state", "=", "draft")],
            )
            add_card(
                "offer_my_rejected",
                _("My Rejected Offers"),
                "zvy.purchase.offer",
                [("create_uid", "=", uid), ("state", "=", "rejected")],
            )
            add_card(
                "offer_my_in_review",
                _("My In Review Offers"),
                "zvy.purchase.offer",
                [("create_uid", "=", uid), ("state", "=", "in_review")],
            )

        if user.has_group("zvy_purchase.group_commission_manager"):
            add_card(
                "case_in_review",
                _("Cases In Review"),
                "zvy.purchase.commission.case",
                [("state", "=", "in_review")],
            )
            add_card(
                "tender_in_review",
                _("Tenders In Review"),
                "zvy.purchase.tender",
                [("state", "=", "in_review")],
            )
            add_card(
                "tender_published",
                _("Tenders Published"),
                "zvy.purchase.tender",
                [("state", "=", "published")],
            )
            add_card(
                "tender_evaluation",
                _("Tenders Evaluation"),
                "zvy.purchase.tender",
                [("state", "=", "evaluation")],
            )

        if user.has_group("zvy_purchase.group_commission_expert"):
            add_card(
                "tender_my_assigned",
                _("My Tenders Assigned"),
                "zvy.purchase.tender",
                [("commission_expert_id", "=", uid), ("state", "=", "assigned")],
            )
            add_card(
                "tender_my_scheduled",
                _("My Tenders Scheduled"),
                "zvy.purchase.tender",
                [("commission_expert_id", "=", uid), ("state", "=", "scheduled")],
            )
            add_card(
                "case_my_in_review",
                _("My Cases In Review"),
                "zvy.purchase.commission.case",
                [("commission_expert_ids", "in", uid), ("state", "=", "in_review")],
            )

        return cards
