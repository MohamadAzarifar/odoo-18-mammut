# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    documents_folder_id = fields.Many2one(
        'documents.document',
        string='Documents Folder',
        copy=False,
        domain="[('type', '=', 'folder')]",
        ondelete='set null',
    )

    def _get_approval_root_folder(self):
        self.ensure_one()
        return self.company_id.approvals_folder_id

    def _get_request_folder_display_name(self):
        self.ensure_one()
        root = self._get_approval_root_folder()
        base = self.name or _('New Request (#%s)', self.id)
        if not root:
            return base
        exclude_id = self.documents_folder_id.id if self.documents_folder_id else 0
        conflict = self.env['documents.document'].sudo().search([
            ('folder_id', '=', root.id),
            ('name', '=', base),
            ('type', '=', 'folder'),
            ('id', '!=', exclude_id),
        ], limit=1)
        if conflict:
            return f'{base} (#{self.id})'
        return base

    def _create_missing_request_folder(self):
        self.ensure_one()
        if not self.company_id.documents_approvals_settings:
            return
        root = self._get_approval_root_folder()
        if not root:
            return
        if self.documents_folder_id:
            return
        folder_name = self._get_request_folder_display_name()
        folder = self.env['documents.document'].sudo().create({
            'name': folder_name,
            'type': 'folder',
            'folder_id': root.id,
            'company_id': self.company_id.id,
            'access_via_link': 'none',
            'access_internal': 'none',
            'owner_id': self.env.ref('base.user_root').id,
        })
        self.documents_folder_id = folder

    def _rename_documents_folder_to_match(self):
        self.ensure_one()
        if not self.documents_folder_id:
            return
        new_name = self._get_request_folder_display_name()
        if self.documents_folder_id.name != new_name:
            self.documents_folder_id.sudo().write({'name': new_name})

    def _get_document_folder(self):
        self.ensure_one()
        root = super()._get_document_folder()
        if not root:
            return self.env['documents.document']
        self._create_missing_request_folder()
        return self.documents_folder_id or root

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals:
            for request in self:
                request._rename_documents_folder_to_match()
        return res

    def action_get_attachment_view(self):
        res = super().action_get_attachment_view()
        if not isinstance(res, dict) or res.get('res_model') != 'documents.document':
            return res
        if not self[:1].company_id.documents_approvals_settings:
            return res
        first = self[0]
        first._create_missing_request_folder()
        if first.documents_folder_id:
            ctx = dict(res.get('context') or {})
            ctx['searchpanel_default_folder_id'] = first.documents_folder_id.id
            ctx.setdefault('default_res_model', 'approval.request')
            ctx.setdefault('default_res_id', first.id)
            res['context'] = ctx
        return res
