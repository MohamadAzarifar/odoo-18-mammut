# -*- coding: utf-8 -*-

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    request_status = fields.Selection(selection_add=[('editing', 'Editing')])
    approval_ext_in_editing = fields.Boolean(
        string='Returned for editing',
        default=False,
        copy=False,
    )
    approval_ext_can_return_for_edit = fields.Boolean(
        compute='_compute_approval_ext_can_return_for_edit',
    )
    approval_ext_requester_can_edit = fields.Boolean(
        string='Requester Can Edit',
        compute='_compute_approval_ext_requester_can_edit',
    )

    @api.depends('request_status', 'request_owner_id')
    @api.depends_context('uid')
    def _compute_approval_ext_requester_can_edit(self):
        """In 'editing', only the request owner may edit or submit."""
        for request in self:
            if request.request_status == 'new':
                request.approval_ext_requester_can_edit = True
            elif request.request_status == 'editing':
                request.approval_ext_requester_can_edit = (
                    request.request_owner_id == self.env.user
                )
            else:
                request.approval_ext_requester_can_edit = False

    @api.depends('request_status', 'approver_ids.status')
    @api.depends_context('uid')
    def _compute_approval_ext_can_return_for_edit(self):
        for request in self:
            request.approval_ext_can_return_for_edit = request._approval_ext_can_return_for_edit()

    def _approval_ext_can_return_for_edit(self):
        self.ensure_one()
        if self.request_status != 'pending':
            return False
        line = self.approver_ids.filtered(lambda a: a.user_id == self.env.user)[:1]
        if not line:
            return False
        return line.status not in ('approved', 'refused', 'cancel')

    @api.depends('approver_ids.status', 'approver_ids.required', 'approval_ext_in_editing')
    def _compute_request_status(self):
        super()._compute_request_status()
        for request in self.filtered('approval_ext_in_editing'):
            request.request_status = 'editing'

    def _approval_ext_check_requester_can_edit(self):
        for request in self.filtered(lambda r: r.request_status == 'editing'):
            if request.request_owner_id != self.env.user:
                raise UserError(
                    _('Only the request owner can modify or submit this request while it is being edited.')
                )

    def write(self, vals):
        if not self.env.su:
            self._approval_ext_check_requester_can_edit()
        return super().write(vals)

    def action_confirm(self):
        self._approval_ext_check_requester_can_edit()
        self.filtered('approval_ext_in_editing').write({'approval_ext_in_editing': False})
        return super().action_confirm()

    def action_withdraw(self, approver=None):
        raise UserError(_('Withdraw is no longer available. Use "Return for editing" if you need changes from the requester.'))

    def action_open_return_to_edit_wizard(self):
        self.ensure_one()
        if not self._approval_ext_can_return_for_edit():
            raise UserError(_('You cannot send this request back for editing.'))
        return {
            'name': _('Return for editing'),
            'type': 'ir.actions.act_window',
            'res_model': 'approval.return.to.edit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def approval_ext_apply_return_to_editing(self, reason_text):
        self.ensure_one()
        if not self._approval_ext_can_return_for_edit():
            raise UserError(_('You cannot send this request back for editing.'))
        reason_text = (reason_text or '').strip()
        if not reason_text:
            raise UserError(_('Please provide a reason.'))

        self._cancel_activities()
        self.mapped('approver_ids').sudo().write({'status': 'new'})
        self.sudo().write({
            'approval_ext_in_editing': True,
            'date_confirmed': False,
        })

        title = escape(_('Returned for editing'))
        reason_block = escape(reason_text)
        intro = escape(
            _(
                '%(name)s asked you to update and resubmit this request.',
                name=self.env.user.display_name,
            )
        )
        body = Markup(
            '<p><strong>%s</strong></p>'
            '<p>%s</p>'
            '<div class="alert alert-warning o_mail_note" role="alert">%s</div>'
        ) % (title, intro, reason_block)
        self.message_post(body=body, message_type='comment', subtype_xmlid='mail.mt_note')
