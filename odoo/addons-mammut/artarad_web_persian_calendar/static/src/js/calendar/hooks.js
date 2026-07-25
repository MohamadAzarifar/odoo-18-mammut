import * as hooks from "@web/views/calendar/hooks";
import { loadBundle } from "@web/core/assets";
import {
    onMounted,
    onPatched,
    onWillStart,
    onWillUnmount,
    useComponent,
    useRef,
} from "@odoo/owl";

hooks.useFullCalendar = function useFullCalendar(refName, params) {
    const component = useComponent();
    const ref = useRef(refName);
    let instance = null;

    function boundParams() {
        const newParams = {};
        for (const key in params) {
            const value = params[key];
            newParams[key] = typeof value === "function" ? value.bind(component) : value;
        }
        return newParams;
    }

    onWillStart(async () => odoo.user_calendar_type === "jalaali" ? await loadBundle("web.jfullcalendar_lib") : await loadBundle("web.fullcalendar_lib"));

    onMounted(() => {
        try {
            instance = (odoo.user_calendar_type === "jalaali" ? new jFullCalendar.Calendar(ref.el, boundParams()) : new FullCalendar.Calendar(ref.el, boundParams()));
            instance.render();
        } catch (e) {
            throw new Error(`Cannot instantiate FullCalendar\n${e.message}`);
        }
    });

    onPatched(() => {
        instance.refetchEvents();
        instance.setOption("weekends", component.props.isWeekendVisible);
        if (params.weekNumbers && component.props.model.scale === "year") {
            instance.destroy();
            instance.render();
        }
    });
    onWillUnmount(() => {
        instance.destroy();
    });

    return {
        get api() {
            return instance;
        },
        get el() {
            return ref.el;
        },
    };
}