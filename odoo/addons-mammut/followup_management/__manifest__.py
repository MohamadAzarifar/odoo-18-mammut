# -*- coding: utf-8 -*-
{
    'name': 'Follow Up Management',
    'version': '18.0.1.0.10',
    'category': 'Sales/CRM',
    'summary': 'Manage customer follow-up records with call history and surveys',
    'description': '''
Follow Up Management
====================
Manage customer follow-up records with:
- Follow-up types with linked survey templates
- Call history tracking
- Conditional type-specific tabs (Delivery, On-site Service, Remote Service)
- Survey integration for customer feedback
    ''',
    'depends': ['survey', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/followup_sequence_data.xml',
        'data/followup_call_status_data.xml',
        'data/followup_type_data.xml',
        'views/followup_call_status_views.xml',
        'views/followup_type_views.xml',
        'views/followup_record_views.xml',
        'views/survey_survey_views.xml',
        'views/survey_templates.xml',
        'report/followup_report_search_views.xml',
        'report/followup_report_over_time_views.xml',
        'report/followup_report_surveys_completed_views.xml',
        'report/followup_report_survey_scores_views.xml',
        'report/followup_report_survey_scores_trend_views.xml',
        'report/followup_report_by_status_views.xml',
        'report/followup_report_by_type_views.xml',
        'report/followup_report_survey_pivot_views.xml',
        'views/followup_menu.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
