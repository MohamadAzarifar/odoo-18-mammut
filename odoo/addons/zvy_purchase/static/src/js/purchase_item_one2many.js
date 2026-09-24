/** @odoo-module */

import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

export class OpenFormX2ManyField extends X2ManyField {
    async openRecord(record) {
        return this.switchToForm(record);
    }

    async onAdd() {
        await this.props.record.save();
        if (!this.props.record.resId) {
            return;
        }
        const inverseField = this.props.record.fields[this.props.name].relation_field;
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: this.props.string,
            res_model: this.list.resModel,
            views: [[false, "form"]],
            target: "current",
            context: {
                [`default_${inverseField}`]: this.props.record.resId,
            },
        });
    }
}

registry.category("fields").add("zvy_open_form_one2many", {
    ...x2ManyField,
    component: OpenFormX2ManyField,
});
