# -*- coding: utf-8 -*-
{
    'name': "Artarad Web Persian Calendar",

    'summary': 
        """
        Persian Calendar in Odoo V18
        """,

    'description':
        """
            This module allows users to select Jalaali or Gregorian calendars regardless of selected language.
            Supported in: tree/form/kanban/pivot/gantt/graph/calendar/search views and chatter.
        """,

    'author': "Artarad Team",
    
    'website': "https://www.artadoo.ir",

    'license': 'LGPL-3',

    'category': 'web',
    
    'version': '18.1.1',

    'depends': ['web', 'mail' ,'base_import', 'calendar', 'web_gantt'],

    'external_dependencies': {
        'python': ['jdatetime', 'num2fawords']
    },

    'data': [
        'data/g2j.sql',
        'views/res_users_view.xml',
        'views/ir_sequence_views.xml',
    ],

    'assets': {
        "web._assets_core": [
            # for all
            ('before', 'web/static/src/session.js', 'artarad_web_persian_calendar/static/src/js/odoo.js',),
            ('after', 'web/static/lib/luxon/luxon.js', 'artarad_web_persian_calendar/static/src/js/luxon-jalaali.js',),
            ('after', 'web/static/src/core/l10n/dates.js', 'artarad_web_persian_calendar/static/src/js/dates.js'),
            
            # for datetime picker
            ('after', 'web/static/src/core/datetime/datetime_picker.js', 'artarad_web_persian_calendar/static/src/js/datetimepicker/datetime_picker.js')
        ],

        'web.assets_frontend': [
            ('after', 'web/static/lib/luxon/luxon.js', 'artarad_web_persian_calendar/static/src/js/luxon-jalaali.js',),
        ],

        'web.assets_backend': [
            # for search
            ('after', 'web/static/src/search/utils/dates.js', 'artarad_web_persian_calendar/static/src/js/search/dates.js',),

            # for calendar view
            ('after', 'web/static/src/views/*/**', 'artarad_web_persian_calendar/static/src/js/calendar/calendar_common_renderer.js',),
            ('after', 'web/static/src/views/*/**', 'artarad_web_persian_calendar/static/src/js/calendar/calendar_year_renderer.js',),
            ('after', 'web/static/src/views/*/**', 'artarad_web_persian_calendar/static/src/js/calendar/calendar_controller.js',),
            ('after', 'web/static/src/views/*/**', 'artarad_web_persian_calendar/static/src/js/calendar/utils.js',),
            ('after', 'web/static/src/views/*/**', 'artarad_web_persian_calendar/static/src/js/calendar/hooks.js',),
        ],

        # for calendar view
        'web.jfullcalendar_lib' : [
            '/artarad_web_persian_calendar/static/src/js/calendar/jfullcalendar/core/index.global.js',
            '/artarad_web_persian_calendar/static/src/js/calendar/jfullcalendar/core/locales-all.global.js',
            '/artarad_web_persian_calendar/static/src/js/calendar/jfullcalendar/interaction/index.global.js',
            '/artarad_web_persian_calendar/static/src/js/calendar/jfullcalendar/daygrid/index.global.js',
            '/artarad_web_persian_calendar/static/src/js/calendar/jfullcalendar/luxon3/index.global.js',
            '/artarad_web_persian_calendar/static/src/js/calendar/jfullcalendar/timegrid/index.global.js',
            '/artarad_web_persian_calendar/static/src/js/calendar/jfullcalendar/list/index.global.js',
        ],

        'web.assets_backend_lazy': [
            # for gantt
            ('after', 'web_gantt/static/src/gantt_arch_parser.js', 'artarad_web_persian_calendar/static/src/js/gantt/gantt_arch_parser.js',),
            ('after', 'web_gantt/static/src/gantt_helpers.js', 'artarad_web_persian_calendar/static/src/js/gantt/gantt_helpers.js',),
            ('after', 'web_gantt/static/src/gantt_renderer_controls.js', 'artarad_web_persian_calendar/static/src/js/gantt/gantt_renderer_controls.js',),
        ],
    },

    'installable': True,

    'auto_install': False,
}
