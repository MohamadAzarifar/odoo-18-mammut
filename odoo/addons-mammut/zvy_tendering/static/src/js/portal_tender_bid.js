/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.PortalTenderBidForm = publicWidget.Widget.extend({
    selector: ".o_portal_tender_bid_form",
    events: {
        "input #amount": "_onAmountInput",
    },

    start() {
        const def = this._super(...arguments);
        this._amountPreviewTimer = null;
        this._refreshAmountPreview();
        return def;
    },

    destroy() {
        if (this._amountPreviewTimer) {
            clearTimeout(this._amountPreviewTimer);
            this._amountPreviewTimer = null;
        }
        return this._super(...arguments);
    },

    _onAmountInput() {
        if (this._amountPreviewTimer) {
            clearTimeout(this._amountPreviewTimer);
        }
        this._amountPreviewTimer = setTimeout(() => {
            this._refreshAmountPreview();
        }, 300);
    },

    async _refreshAmountPreview() {
        const amountInput = this.el.querySelector("#amount");
        const formattedEl = this.el.querySelector(".o_bid_amount_formatted");
        const wordsEl = this.el.querySelector(".o_bid_amount_words");
        if (!amountInput || (!formattedEl && !wordsEl)) {
            return;
        }
        const envelopeId = this.el.dataset.envelopeId;
        if (!envelopeId) {
            return;
        }
        const amount = amountInput.value;
        let result = { formatted: "", words: "" };
        if (amount) {
            result = await rpc(`/my/tenders/${envelopeId}/amount_preview`, {
                amount,
                access_token: this.el.dataset.accessToken || undefined,
            });
        }
        if (formattedEl) {
            formattedEl.textContent = result.formatted || "";
        }
        if (wordsEl) {
            wordsEl.textContent = result.words || "";
        }
    },
});
