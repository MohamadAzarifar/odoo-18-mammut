# -*- coding: utf-8 -*-

from odoo import _
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class ZvyPurchasePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "tender_count" in counters:
            Tender = request.env["zvy.purchase.tender"]
            values["tender_count"] = (
                Tender.search_count(Tender._zvy_portal_vendor_domain())
                if Tender.has_access("read")
                else 0
            )
        return values

    def _zvy_portal_get_tender(self, tender_id):
        """Ensure the portal user can read the tender; return it in user env."""
        try:
            self._document_check_access("zvy.purchase.tender", tender_id)
        except (AccessError, MissingError):
            raise
        return request.env["zvy.purchase.tender"].browse(tender_id)

    def _zvy_prepare_tender_portal_rendering_values(
        self, page=1, date_begin=None, date_end=None, sortby=None, **kwargs
    ):
        Tender = request.env["zvy.purchase.tender"]
        domain = Tender._zvy_portal_vendor_domain()

        searchbar_sortings = {
            "date": {"label": _("Newest"), "order": "id desc"},
            "name": {"label": _("Reference"), "order": "name asc, id asc"},
            "end_date": {"label": _("End Date"), "order": "end_date asc, id asc"},
        }
        if not sortby:
            sortby = "date"
        order = searchbar_sortings[sortby]["order"]

        if date_begin and date_end:
            domain += [
                ("create_date", ">", date_begin),
                ("create_date", "<=", date_end),
            ]

        total = Tender.search_count(domain)
        pager = portal_pager(
            url="/my/tenders",
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
            },
            total=total,
            page=page,
            step=self._items_per_page,
        )
        tenders = Tender.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        request.session["my_tenders_history"] = tenders.ids[:100]

        return {
            "tenders": tenders,
            "page_name": "tender",
            "pager": pager,
            "default_url": "/my/tenders",
            "searchbar_sortings": searchbar_sortings,
            "sortby": sortby,
        }

    def _zvy_tender_get_page_view_values(self, tender, **kwargs):
        offers = tender._zvy_portal_vendor_offers()
        values = {
            "tender": tender,
            "offers": offers,
            "bidding_open": tender._zvy_portal_bidding_open(),
            "page_name": "tender",
        }
        return self._get_page_view_values(
            tender, None, values, "my_tenders_history", False, **kwargs
        )

    @route(
        ["/my/tenders", "/my/tenders/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_tenders(self, **kwargs):
        values = self._zvy_prepare_tender_portal_rendering_values(**kwargs)
        return request.render("zvy_purchase.portal_my_tenders", values)

    @route(
        ["/my/tenders/<int:tender_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_tender(self, tender_id, **kwargs):
        try:
            tender = self._zvy_portal_get_tender(tender_id)
        except (AccessError, MissingError):
            return request.redirect("/my")

        values = self._zvy_tender_get_page_view_values(tender, **kwargs)
        if kwargs.get("success"):
            values["success"] = True
        if kwargs.get("error"):
            values["error"] = True
        return request.render("zvy_purchase.portal_my_tender", values)

    @route(
        ["/my/tenders/<int:tender_id>/offer/<int:offer_id>"],
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
    )
    def portal_my_tender_update_offer(self, tender_id, offer_id, **post):
        try:
            tender = self._zvy_portal_get_tender(tender_id)
        except (AccessError, MissingError):
            return request.redirect("/my")

        offer = tender._zvy_portal_vendor_offers().filtered(
            lambda o: o.id == offer_id
        )[:1]
        if not offer:
            return request.redirect(f"/my/tenders/{tender_id}")

        vals = {}
        for field_name in offer._PORTAL_BID_FIELDS:
            if field_name not in post:
                continue
            raw = post.get(field_name)
            if field_name in (
                "unit_price",
                "quantity",
                "discount_percent_per_unit",
            ):
                try:
                    vals[field_name] = float(raw or 0.0)
                except (TypeError, ValueError):
                    return request.redirect(
                        f"/my/tenders/{tender_id}?error=1"
                    )
            elif field_name == "deliver_time":
                vals[field_name] = raw or False
            else:
                vals[field_name] = raw or False

        try:
            offer._zvy_portal_update_bid(vals)
        except (AccessError, UserError):
            return request.redirect(f"/my/tenders/{tender_id}?error=1")

        return request.redirect(f"/my/tenders/{tender_id}?success=1")
