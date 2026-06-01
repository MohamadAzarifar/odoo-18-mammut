# -*- coding: utf-8 -*-
{
    'name': 'Approvals Documents Extension',
    'version': '18.0.2.0.7',
    'category': 'Productivity/Documents',
    'summary': 'Approvals: Documents folders + editing / restart workflow',
    'description': '''
Approvals enhancements:
- File attachments under Approval / {reference} when Documents centralization is on.
- "Editing" state: approvers may return the request to the creator with a reason,
  restarting approvals from scratch. Withdraw on requests is disabled.
''',
    'assets': {
        'web.assets_backend': [
            'approval_ext/static/src/widgets/attach_document_stat.scss',
            'approval_ext/static/src/widgets/attach_document_stat.js',
        ],
    },
    'depends': ['documents_approvals', 'approvals'],
    'data': [
        'security/approval_security.xml',
        'security/ir.model.access.csv',
        'wizard/approval_return_to_edit_wizard_views.xml',
        'data/documents_folder_data.xml',
        'views/approval_request_workflow_views.xml',
        'views/approval_request_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'license': 'LGPL-3',
    'application': False,
}
