/** @odoo-module **/
import * as dates from "@web/core/l10n/dates";
import { memoize } from "@web/core/utils/functions";

function insert_at_string(main_string, index, inserting_string) {
    return main_string.substr(0, index) + inserting_string + main_string.substr(index);
}

function put_j(fmt) {
    var index;
    // find index of first 'y' and put 'j' before it
    index = fmt.indexOf('y');
    if (index !== -1) { fmt = insert_at_string(fmt, index, 'j'); }
    // find index of first 'm' or 'M' and put 'j' before it
    index = fmt.indexOf('M');
    if (index !== -1) { fmt = insert_at_string(fmt, index, 'j'); }
    // find index of first 'm' or 'M' and put 'j' before it
    index = fmt.indexOf('d');
    if (index !== -1) { fmt = insert_at_string(fmt, index, 'j'); }

    return fmt;
}

const originalStrftimeToLuxonFormat = dates.strftimeToLuxonFormat;
dates.strftimeToLuxonFormat = memoize(function strftimeToLuxonFormat(value) {
    var fmt = originalStrftimeToLuxonFormat(value);
    if (odoo.user_calendar_type === "jalaali") {
        fmt = put_j(fmt);
    }
    return fmt;
});

const originalGetLocalYearAndWeek = dates.getLocalYearAndWeek;
dates.getLocalYearAndWeek = function(date) {
    if (odoo.user_calendar_type === "jalaali") {
        if (!date.isLuxonDateTime) {
            date = DateTime.fromJSDate(date);
        }
        return { year: date.jyear, week: date.jweekNumber };
    }
    else {
        return originalGetLocalYearAndWeek.call(this, date);
    }
}