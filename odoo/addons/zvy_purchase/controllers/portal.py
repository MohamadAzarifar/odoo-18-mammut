# -*- coding: utf-8 -*-

import re

from odoo import _, fields
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request, route
from odoo.tools.misc import format_date
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

    def _zvy_portal_lang(self):
        """Language record used for portal formatting (website lang, then user)."""
        lang = getattr(request, "lang", None)
        # On website, request.lang is LangData (has .id / .code), not a code string.
        if lang is not None and hasattr(lang, "id"):
            return request.env["res.lang"].browse(lang.id)
        lang_code = request.env.user.lang or "en_US"
        return request.env["res.lang"]._lang_get(lang_code)

    def _zvy_portal_use_jalali(self):
        """Whether portal dates should display in the Jalali calendar."""
        user = request.env.user
        if "calendar_type" in user._fields and user.calendar_type == "jalaali":
            return True
        lang = getattr(request, "lang", None)
        code = getattr(lang, "code", None) or user.lang or ""
        return str(code).startswith("fa")

    def _zvy_format_portal_date(self, value):
        """Format a date for the portal datepicker input (Jalali when applicable)."""
        if not value:
            return ""
        if isinstance(value, str):
            value = fields.Date.to_date(value)
        use_jalali = self._zvy_portal_use_jalali()
        if use_jalali:
            import jdatetime

            return jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d")
        return format_date(request.env, value)

    def _zvy_parse_portal_date(self, raw):
        """Parse portal date input (ISO or Jalali YYYY/MM/DD) to a Date value."""
        if raw is None or raw is False:
            return False
        s = str(raw).strip()
        if not s:
            return False
        # Prefer ISO / server date (JS datetime-picker serializes to this).
        try:
            return fields.Date.to_date(s)
        except (ValueError, TypeError):
            pass
        match = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
        if not match:
            raise ValueError(f"Invalid date: {s}")
        year, month, day = map(int, match.groups())
        # Jalali years are typically 1300–1500 in this century.
        if self._zvy_portal_use_jalali() and year < 1700:
            import jdatetime

            return jdatetime.date(year, month, day).togregorian()
        return fields.Date.to_date(f"{year:04d}-{month:02d}-{day:02d}")

    def _zvy_format_portal_float(self, value, digits=2):
        """Format a float with locale thousand separators for portal inputs."""
        lang = self._zvy_portal_lang()
        fmt = f"%.{int(digits)}f"
        formatted = lang.format(fmt, float(value or 0.0), grouping=True)
        if digits:
            # Drop trailing zeros after the decimal for cleaner input values.
            decimal = lang.decimal_point or "."
            if decimal in formatted:
                int_part, frac_part = formatted.rsplit(decimal, 1)
                frac_part = frac_part.rstrip("0")
                formatted = int_part if not frac_part else f"{int_part}{decimal}{frac_part}"
        return formatted

    def _zvy_parse_portal_float(self, raw):
        """Parse a locale-formatted float (e.g. 10,000,000.5) to float."""
        if raw is None or raw is False or raw == "":
            return 0.0
        lang = self._zvy_portal_lang()
        s = str(raw).strip()
        thousands = lang.thousands_sep or ""
        decimal = lang.decimal_point or "."
        if thousands:
            s = s.replace(thousands, "")
        s = s.replace("\u00a0", "").replace("\u066c", "").replace(" ", "")
        if decimal and decimal != ".":
            s = s.replace(decimal, ".")
        # Fallback: remove leftover grouping commas
        if s.count(".") <= 1:
            s = re.sub(r",(?=\d{3}(\D|$))", "", s)
        return float(s)

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
        format_unit_price = {}
        format_deliver_time = {}
        for offer in offers:
            digits = offer.currency_id.decimal_places if offer.currency_id else 2
            format_unit_price[offer.id] = self._zvy_format_portal_float(
                offer.unit_price, digits=digits
            )
            format_deliver_time[offer.id] = self._zvy_format_portal_date(
                offer.deliver_time
            )
        values = {
            "tender": tender,
            "offers": offers,
            "bidding_open": tender._zvy_portal_bidding_open(),
            "page_name": "tender",
            "format_unit_price": format_unit_price,
            "format_deliver_time": format_deliver_time,
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
                    value = self._zvy_parse_portal_float(raw)
                except (TypeError, ValueError):
                    return request.redirect(
                        f"/my/tenders/{tender_id}?error=1"
                    )
                # Portal shows discount as percentage points (10); store as rate (0.1).
                if field_name == "discount_percent_per_unit":
                    value = value / 100.0
                vals[field_name] = value
            elif field_name == "deliver_time":
                try:
                    vals[field_name] = self._zvy_parse_portal_date(raw)
                except (TypeError, ValueError):
                    return request.redirect(
                        f"/my/tenders/{tender_id}?error=1"
                    )
            else:
                vals[field_name] = raw or False

        try:
            offer._zvy_portal_update_bid(vals)
        except (AccessError, UserError, ValidationError):
            return request.redirect(f"/my/tenders/{tender_id}?error=1")

        return request.redirect(f"/my/tenders/{tender_id}?success=1")
