/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { parseDate, serializeDate } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";

/**
 * Portal tender bid form:
 * - unit price keeps locale thousand separators while typing
 * - delivery date uses Odoo datetime-picker (Jalali when calendar is jalaali)
 * - on submit, strip separators and serialize date to ISO for the server
 */
publicWidget.registry.ZvyPortalTenderOfferForm = publicWidget.Widget.extend({
    selector: ".o_portal_tender_offer_form",
    events: {
        "input .o_zvy_unit_price_input": "_onUnitPriceInput",
        "blur .o_zvy_unit_price_input": "_onUnitPriceBlur",
        submit: "_onSubmit",
    },

    start() {
        const priceInput = this.el.querySelector(".o_zvy_unit_price_input");
        if (priceInput && priceInput.value) {
            priceInput.value = this._formatAmount(this._parseAmount(priceInput.value));
        }
        return this._super(...arguments);
    },

    _thousandsSep() {
        return localization.thousandsSep || ",";
    },

    _decimalPoint() {
        return localization.decimalPoint || ".";
    },

    _parseAmount(raw) {
        if (raw === undefined || raw === null || raw === "") {
            return NaN;
        }
        let s = String(raw).trim();
        const thousands = this._thousandsSep();
        const decimal = this._decimalPoint();
        if (thousands) {
            s = s.split(thousands).join("");
        }
        // Common extras: spaces, NBSP, Arabic thousands separator
        s = s.replace(/[\s\u00a0\u066c]/g, "");
        if (decimal && decimal !== ".") {
            s = s.replace(decimal, ".");
        }
        // Drop leftover grouping commas when locale sep was already removed
        if ((s.match(/\./g) || []).length <= 1) {
            s = s.replace(/,(?=.*\.)/g, "").replace(/,(?!\d{1,2}$)/g, "");
        }
        return Number(s);
    },

    _formatAmount(value) {
        if (value === undefined || value === null || Number.isNaN(value)) {
            return "";
        }
        const abs = Math.abs(value);
        const [intPart, fracPart] = String(abs).split(".");
        const thousands = this._thousandsSep();
        const decimal = this._decimalPoint();
        const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, thousands);
        const sign = value < 0 ? "-" : "";
        if (fracPart === undefined) {
            return sign + grouped;
        }
        return `${sign}${grouped}${decimal}${fracPart}`;
    },

    _onUnitPriceInput(ev) {
        const input = ev.currentTarget;
        const start = input.selectionStart;
        const before = input.value;
        // Keep only digits, locale decimal, and minus while typing
        const decimal = this._decimalPoint();
        const escapedDec = decimal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const cleaned = before.replace(new RegExp(`[^0-9\\-${escapedDec}]`, "g"), "");
        if (cleaned !== before) {
            input.value = cleaned;
            const delta = before.length - cleaned.length;
            const pos = Math.max(0, (start || 0) - delta);
            input.setSelectionRange(pos, pos);
        }
    },

    _onUnitPriceBlur(ev) {
        const input = ev.currentTarget;
        const num = this._parseAmount(input.value);
        if (!Number.isNaN(num)) {
            input.value = this._formatAmount(num);
        }
    },

    _onSubmit() {
        const priceInput = this.el.querySelector(".o_zvy_unit_price_input");
        if (priceInput) {
            const num = this._parseAmount(priceInput.value);
            priceInput.value = Number.isNaN(num) ? "" : String(num);
        }
        const dateInput = this.el.querySelector(".o_zvy_deliver_time_input");
        if (dateInput && dateInput.value) {
            const date = parseDate(dateInput.value);
            if (date && date.isValid) {
                dateInput.value = serializeDate(date);
            }
        }
    },
});
