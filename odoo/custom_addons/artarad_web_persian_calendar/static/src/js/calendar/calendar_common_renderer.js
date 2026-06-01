/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";

const { DateTime } = luxon;

patch(CalendarCommonRenderer.prototype, {

    headerTemplateProps(date) {
        if(odoo.user_calendar_type === "jalaali") {
            const scale = this.props.model.scale;
            const options = scale === "month" ? { zone: "UTC" } : {};
            const { weekdayShort, weekdayLong, jday } = DateTime.fromJSDate(date, options);
            return {
                weekdayShort,
                weekdayLong,
                day: jday,
                scale,
            };
        }
        return super.headerTemplateProps(date);
    }
});