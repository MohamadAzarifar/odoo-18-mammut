/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CalendarController } from "@web/views/calendar/calendar_controller";

patch(CalendarController.prototype, {

    get currentDate() {
        if(odoo.user_calendar_type === "jalaali") {
            const meta = this.model.meta;
            const scale = meta.scale;
            if (this.env.isSmall && ["week", "month"].includes(scale)) {
                const date = meta.date || DateTime.now();
                let text = "";
                if (scale === "week") {
                    const startMonth = date.startOf("week");
                    const endMonth = date.endOf("week");
                    if (startMonth.toFormat("jLLL") !== endMonth.toFormat("jLLL")) {
                        text = `${startMonth.toFormat("jLLL")}-${endMonth.toFormat("jLLL")}`;
                    } else {
                        text = startMonth.toFormat("jLLLL");
                    }
                } else if (scale === "month") {
                    text = date.toFormat("jLLLL");
                }
                return ` - ${text} ${date.jyear}`;
            } else {
                return "";
            }
        }
        return super.currentDate;
    },

    get today() {
        if(odoo.user_calendar_type === "jalaali") {
            return this.date.toFormat("jd");
        }
        return super.today;
    },

    get currentYear() {
        if(odoo.user_calendar_type === "jalaali") {
            return this.date.toFormat("jy");
        }
        return super.currentYear;
    },

    get dayHeader() {
        if(odoo.user_calendar_type === "jalaali") {
            return this.date.toFormat("jd jMMMM jy");
        }
        return super.dayHeader;
    },

    get weekHeader() {
        if(odoo.user_calendar_type === "jalaali") {
            const { rangeStart, rangeEnd } = this.model;
            if (rangeStart.jyear != rangeEnd.jyear) {
                return `${rangeStart.toFormat("jMMMM")} ${rangeStart.year} - ${rangeEnd.toFormat(
                    "jMMMM"
                )} ${rangeEnd.jyear}`;
            } else if (rangeStart.jmonth != rangeEnd.jmonth) {
                return `${rangeStart.toFormat("jMMMM")} - ${rangeEnd.toFormat("jMMMM")} ${
                    rangeStart.jyear
                }`;
            }
            return `${rangeStart.toFormat("jMMMM")} ${rangeStart.jyear}`;
        }
        return super.weekHeader;
    },

    get currentMonth() {
        if(odoo.user_calendar_type === "jalaali") {
            return `${this.date.toFormat("jMMMM")} ${this.date.jyear}`;
        }
        return super.currentMonth;
    },

    get currentWeek() {
        if(odoo.user_calendar_type === "jalaali") {
            return this.date.toFormat("jW");
        }
        return super.currentWeek;
    },

    async setDate(move) {
        if(odoo.user_calendar_type === "jalaali") {
            let date = null;
            switch (move) {
                case "next":
                    date = this.model.date.plus({ [`${"j" + this.model.scale}s`]: 1 });
                    break;
                case "previous":
//                    date = this.model.date.minus({ [`${"j" + this.model.scale}s`]: 1 });
                    date = this.model.date.plus({ [`${"j" + this.model.scale}s`]: -1 });
                    break;
                case "today":
                    date = luxon.DateTime.local().startOf("day");
                    break;
            }
            await this.model.load({ date });
        }
        else {
            super.setDate(move);
        }
    },
});

