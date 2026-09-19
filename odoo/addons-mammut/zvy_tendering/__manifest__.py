# -*- coding: utf-8 -*-
{
    'name': 'Mammut Procurement & Tendering',
    'version': '18.0.2.13',
    'category': 'Procurement & Tendering',
    'summary': 'Purchase requests, AVL inquiry, holding commission, and closed-envelope tenders',
    'description': """
Mammut Procurement & Tendering
==============================
Standalone procurement workflow: purchase requests, commercial inquiry with AVL,
holding commission review, closed-envelope tenders, and company signatory approvals.
    """,
    'author': 'Mammut',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'product',
        'purchase',
        'approvals',
        'portal',
        'hr',
    ],
    'external_dependencies': {
        'python': ['num2fawords'],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/res_currency_data.xml',
        'data/mail_template_data.xml',
        'views/zvy_avl_views.xml',
        'views/zvy_purchase_request_views.xml',
        'views/zvy_quote_views.xml',
        'views/zvy_commission_views.xml',
        'views/zvy_closed_envelope_views.xml',
        'views/approval_request_views.xml',
        'views/product_template_views.xml',
        'views/zvy_product_procurement_company_views.xml',
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
        'wizard/request_wizard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'zvy_tendering/static/src/js/portal_tender_bid.js',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
