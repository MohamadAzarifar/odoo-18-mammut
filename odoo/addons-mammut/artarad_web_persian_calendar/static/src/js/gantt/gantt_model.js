/** @odoo-module **/
 
import { patch } from "@web/core/utils/patch";
 import * as GM from "@web_gantt/gantt_model"
 import { localization } from "@web/core/l10n/localization";

 GM.computeRange = function(scale, date) {
    if(odoo.user_calendar_type === "jalaali") {
        scale = "j" + scale;
    }

    let start = date;
    let end = date;

    if (scale === "week") {
        // startOf("week") does not depend on locale and will always give the
        // "Monday" of the week... (ISO standard)
        const { weekStart } = localization;
        const weekday = start.weekday < weekStart ? weekStart - 7 : weekStart;
        start = start.set({ weekday }).startOf("day");
        end = start.plus({ weeks: 1, days: -1 }).endOf("day");
    } else {
        start = start.startOf(scale);
        end = end.endOf(scale);
    }

    return { start, end };
}

patch(GM.GanttModel.prototype, {

    _buildMetaData(params = {}) {
        this._nextMetaData = { ...(this._nextMetaData || this.metaData) };

        if (params.groupedBy) {
            this._nextMetaData.groupedBy = params.groupedBy;
        }

        let recomputeRange = false;
        if (params.scaleId) {
            this._nextMetaData.scale = { ...this.metaData.scales[params.scaleId] };
            recomputeRange = true;
        }
        if (params.focusDate) {
            this._nextMetaData.focusDate = params.focusDate;
            recomputeRange = true;
        }

        if ("pagerLimit" in params) {
            this._nextMetaData.pagerLimit = params.pagerLimit;
        }
        if ("pagerOffset" in params) {
            this._nextMetaData.pagerOffset = params.pagerOffset;
        }

        if (recomputeRange) {
            const { dynamicRange, focusDate, scale } = this._nextMetaData;
            if (dynamicRange) {
                this._nextMetaData.startDate = focusDate.startOf(scale.interval);
                this._nextMetaData.stopDate = this._nextMetaData.startDate.plus({
                    [scale.id]: 1,
                    millisecond: -1,
                });
            } else {
                const { start, end } = GM.computeRange(scale.id, focusDate);
                this._nextMetaData.startDate = start;
                this._nextMetaData.stopDate = end;
            }
        }

        return this._nextMetaData;
    },

});
