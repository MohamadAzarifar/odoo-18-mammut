/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.PortalTenderBidForm = publicWidget.Widget.extend({
    selector: ".o_portal_tender_bid_form",
    events: {
        "input .o_bid_line_price": "_onAmountInput",
        "input #amount": "_onAmountInput",
    },

    start() {
        const def = this._super(...arguments);
        this._amountPreviewTimer = null;
        this._refreshAllPreviews();
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
            this._refreshAllPreviews();
        }, 300);
    },

    _refreshAllPreviews() {
        const envelopeId = this.el.dataset.envelopeId;
        if (!envelopeId) {
            return;
        }
        const lineInputs = this.el.querySelectorAll(".o_bid_line_price");
        if (lineInputs.length) {
            lineInputs.forEach((input) => this._refreshInputPreview(envelopeId, input));
            return;
        }
        const amountInput = this.el.querySelector("#amount");
        if (amountInput) {
            this._refreshHeaderPreview(envelopeId, amountInput);
        }
    },

    async _refreshInputPreview(envelopeId, amountInput) {
        const previewEl = amountInput
            .closest("td")
            ?.querySelector(".o_bid_line_preview");
        const amount = amountInput.value;
        let result = { formatted: "", words: "" };
        if (amount) {
            result = await rpc(`/my/tenders/${envelopeId}/amount_preview`, {
                amount,
                access_token: this.el.dataset.accessToken || undefined,
            });
        }
        if (previewEl) {
            const parts = [result.formatted, result.words].filter(Boolean);
            previewEl.textContent = parts.join(" — ");
        }
    },

    async _refreshHeaderPreview(envelopeId, amountInput) {
        const formattedEl = this.el.querySelector(".o_bid_amount_formatted");
        const wordsEl = this.el.querySelector(".o_bid_amount_words");
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
