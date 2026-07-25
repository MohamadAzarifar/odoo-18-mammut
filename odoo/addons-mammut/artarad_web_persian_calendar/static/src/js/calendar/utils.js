import * as utils from "@web/views/calendar/utils";

const originalGetFormattedDateSpan = utils.getFormattedDateSpan;
utils.getFormattedDateSpan = function(start, end) {
    if (odoo.user_calendar_type === "jalaali") {
        const isSameDay = start.hasSame(end, "jdays");
        if (!isSameDay && start.hasSame(end, "jmonth")) {
            // Simplify date-range if an event occurs into the same month (eg. "August 4-5, 2019")
            return start.toFormat("jLLLL jd") + "-" + end.toFormat("jd, jy");
        } else {
            return isSameDay
                ? start.toFormat("jDDD")
                : start.toFormat("jDDD") + " - " + end.toFormat("jDDD");
        }
    }
    else {
        return originalGetFormattedDateSpan.call(this, start, end)
    }
};