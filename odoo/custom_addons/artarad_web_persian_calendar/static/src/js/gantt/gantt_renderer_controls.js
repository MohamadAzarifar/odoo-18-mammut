import { patch } from "@web/core/utils/patch";
import { GanttRendererControls } from "@web_gantt/gantt_renderer_controls";

patch(GanttRendererControls.prototype, {
    get dateDescription() {
        const { focusDate, rangeId } = this.state;
        if (odoo.user_calendar_type === "jalaali" && rangeId === "quarter") {
            return focusDate.toFormat('Qjq jyyyy');
        }
        return super.dateDescription;
    }
});