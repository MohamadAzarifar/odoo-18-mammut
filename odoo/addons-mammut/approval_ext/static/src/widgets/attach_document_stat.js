/** @odoo-module */

import { AttachDocumentWidget } from "@web/views/widgets/attach_document/attach_document";
import { registry } from "@web/core/registry";
import { xml } from "@odoo/owl";

/**
 * Attach control: same height / flex behaviour as other oe_stat_button slots.
 * The FormCompiler adds flex classes on <button> children; <widget> does not, so we set additionalClasses.
 */
export class AttachDocumentStatWidget extends AttachDocumentWidget {
    static template = xml`
        <button
            type="button"
            class="oe_stat_button btn btn-primary border-0 text-start w-100"
            t-on-click.prevent="triggerUpload">
            <i class="fa fa-paperclip o_button_icon" role="presentation"/>
            <div class="o_stat_info">
                <span class="o_stat_text"><t t-esc="props.string"/></span>
            </div>
        </button>
    `;
}

registry.category("view_widgets").add("attach_document_stat", {
    component: AttachDocumentStatWidget,
    additionalClasses: [
        "d-flex",
        "flex-grow-1",
        "flex-lg-grow-0",
        "mb-0",
        "min-w-0",
        "align-self-stretch",
    ],
    extractProps({ attrs }) {
        const { action, highlight, string } = attrs;
        return {
            action,
            highlight: !!highlight,
            string,
        };
    },
});
