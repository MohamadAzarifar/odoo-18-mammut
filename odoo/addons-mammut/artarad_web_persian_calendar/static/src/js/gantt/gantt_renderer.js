/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { GanttRenderer } from "@web_gantt/gantt_renderer";

patch(GanttRenderer.prototype, {
    getFormattedFocusDate() {
        const { focusDate, scale } = this.model.metaData;
        const { id: scaleId } = scale;
        var res = '\u202B';
        switch (scaleId) {
            case "day":
                res += focusDate.toFormat("jyyyy/jMM/jdd");
                break;
            case "month":
                res += focusDate.toFormat("jMMMM jyyyy");
                break;
            case "year":
                res += focusDate.toFormat("jyyyy");
                break;
            case "week": {
                const { startDate, stopDate } = this.model.metaData;
                res += `${startDate.toFormat("jyyyy/jMM/jdd")} - ${stopDate.toFormat("jyyyy/jMM/jdd")}`;
                break;
            }
            default:
                throw new Error(`Unknown scale id "${scaleId}".`);
        }
        return res + '\u202C';
    }
});