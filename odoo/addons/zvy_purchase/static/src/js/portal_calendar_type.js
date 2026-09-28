/**
 * Expose the user's calendar preference for artarad Jalali patches on the
 * portal/frontend (backend sets this via artarad's odoo.js in _assets_core).
 *
 * Must be a classic script loaded BEFORE web/session.js: that module deletes
 * odoo.__session_info__ after copying it, so a later bootstrap always sees
 * null and wrongly falls back to gregorian (breaking Jalali parse/format).
 */
if (typeof odoo !== "undefined") {
    const info = odoo.__session_info__ || {};
    const lang =
        (info.user_context && info.user_context.lang) ||
        (typeof document !== "undefined" && document.documentElement.lang) ||
        "";
    const fromLang = String(lang).toLowerCase().startsWith("fa");
    odoo.user_calendar_type =
        info.user_calendar_type ||
        odoo.user_calendar_type ||
        (fromLang ? "jalaali" : "gregorian");
}
