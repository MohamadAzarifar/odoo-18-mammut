# -*- coding: utf-8 -*-

from . import hooks
from . import models
from . import wizard


def post_init_hook(env):
    """Odoo 18+: called as post_init_hook(env), not (cr, registry)."""

    folder = env.ref('approval_ext.document_approval_root_folder', raise_if_not_found=False)
    if not folder:
        return

    companies = env['res.company'].sudo().search([])
    companies.write({
        'documents_approvals_settings': True,
        'approvals_folder_id': folder.id,
    })

    docs = env['documents.document'].sudo().search([
        ('res_model', '=', 'approval.request'),
        ('type', '=', 'binary'),
        ('attachment_id', '!=', False),
    ])
    Approval = env['approval.request'].sudo()

    docs_by_req = docs.grouped('res_id')
    for res_id in docs_by_req:
        if not res_id:
            continue
        group_docs = docs_by_req[res_id]
        request = Approval.browse(res_id)
        if not request.exists() or not request.company_id.documents_approvals_settings:
            continue
        request._create_missing_request_folder()
        if request.documents_folder_id:
            group_docs.write({'folder_id': request.documents_folder_id.id})

    hooks.unlink_legacy_documents_approvals_workspace(env)
    hooks.apply_security_rules(env)
