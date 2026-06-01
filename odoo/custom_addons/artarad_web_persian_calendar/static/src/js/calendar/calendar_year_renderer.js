/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CalendarYearRenderer } from "@web/views/calendar/calendar_year/calendar_year_renderer";


patch(CalendarYearRenderer.prototype, {
    getDateWithMonth(month) {
        if(odoo.user_calendar_type === "jalaali") {
            return this.props.model.date.set({ jmonth: this.months.indexOf(month) + 1 }).toISO();
        }
        return super.getDateWithMonth(month);
    }
});