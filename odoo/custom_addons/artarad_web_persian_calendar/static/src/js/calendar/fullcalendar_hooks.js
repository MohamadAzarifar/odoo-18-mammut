/** @odoo-module **/

import * as fullcalendar_hooks from "@web/views/calendar/hooks";
import { onMounted, onPatched, onWillStart, onWillUnmount, useComponent, useRef } from "@odoo/owl";
import { loadCSS, loadJS } from "@web/core/assets";

fullcalendar_hooks.useFullCalendar = function useFullCalendar(refName, params) {
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

    async function loadJsFiles() {
        const files = [
            odoo.user_calendar_type === "jalaali" ? "/artarad_web_persian_calendar/static/src/js/calendar/fullcalendar_core_main.js" : "/web/static/lib/fullcalendar/core/main.js",
            "/web/static/lib/fullcalendar/daygrid/main.js",
            "/web/static/lib/fullcalendar/interaction/main.js",
            "/web/static/lib/fullcalendar/luxon/main.js",
            "/web/static/lib/fullcalendar/timegrid/main.js",
            "/web/static/lib/fullcalendar/list/main.js",
        ];
        for (const file of files) {
            await loadJS(file);
        }
    }
    async function loadCssFiles() {
        await Promise.all(
            [
                "/web/static/lib/fullcalendar/core/main.css",
                "/web/static/lib/fullcalendar/daygrid/main.css",
                "/web/static/lib/fullcalendar/timegrid/main.css",
                "/web/static/lib/fullcalendar/list/main.css",
            ].map((file) => loadCSS(file))
        );
    }

    onWillStart(() => Promise.all([loadJsFiles(), loadCssFiles()]));

    onMounted(() => {
        try {
            instance = new FullCalendar.Calendar(ref.el, boundParams());
            instance.render();
        } catch (e) {
            throw new Error(`Cannot instantiate FullCalendar\n${e.message}`);
        }
    });
    onPatched(() => {
        instance.refetchEvents();
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