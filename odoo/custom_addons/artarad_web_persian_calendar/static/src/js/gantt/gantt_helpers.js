import * as helpers from "@web_gantt/gantt_helpers";

const originalDiffColumn = helpers.diffColumn;
helpers.diffColumn = function(col1, col2, unit) {
	if (unit.includes("j")) {
		unit = unit.replace("j", "");
	}
    return Math.round(originalDiffColumn.call(this, col1, col2, unit));
}

const originalGetRangeFromDate = helpers.getRangeFromDate;
helpers.getRangeFromDate = function(rangeId, date) {
    if (odoo.user_calendar_type === "jalaali" && rangeId !== "week") {
        const startDate = date.startOf("j" + rangeId);
        const stopDate = startDate.plus({ ["j" + rangeId]: 1 }).minus({ day: 1 });
        return { focusDate: date, startDate, stopDate, rangeId };
    }
    return originalGetRangeFromDate.call(this, rangeId, date);
}

const originalLocalStartOf = helpers.localStartOf;
helpers.localStartOf = function(date, unit) {
    if (odoo.user_calendar_type === "jalaali") {
        if (unit === "year" || unit === "quarter" || unit === "month") {
            if (!unit.includes("j")){
                unit = "j" + unit;
            }
        }
    }
    return originalLocalStartOf.call(this, date, unit);
}

const originalLocalEndOf = helpers.localEndOf;
helpers.localEndOf = function(date, unit) {
    if (odoo.user_calendar_type === "jalaali") {
        if (unit === "year" || unit === "quarter" || unit === "month") {
            if (!unit.includes("j")){
                unit = "j" + unit;
            }
        }
    }
    return originalLocalEndOf.call(this, date, unit);
}