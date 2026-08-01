# -*- coding: utf-8 -*-
from odoo import _, fields, models


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    zvy_purchase_request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        copy=False,
        index=True,
        ondelete='set null',
    )

    def action_approve(self, approver=None):
        res = super().action_approve(approver=approver)
        for request in self:
            pr = request.zvy_purchase_request_id.sudo()
            if not pr or pr.state != 'signatory':
                continue
            if request.request_status == 'approved':
                pr.write({'state': 'po_ready'})
                pr.message_post(body=_(
                    'Signatory approval completed (%s); ready for PO creation.'
                ) % request.display_name)
        return res

    def action_refuse(self, approver=None):
        res = super().action_refuse(approver=approver)
        for request in self:
            pr = request.zvy_purchase_request_id.sudo()
            if not pr or pr.state != 'signatory':
                continue
            if request.request_status == 'refused':
                reason = self.env.context.get('zvy_refuse_reason') or ''
                pr.write({'state': 'cm_review'})
                body = _(
                    'Signatory approval refused (%s); returned to Commercial Manager.'
                ) % request.display_name
                if reason:
                    body = '%s\n%s' % (body, _('Reason: %s') % reason)
                pr.message_post(body=body)
        return res

    def action_open_zvy_purchase_request(self):
        self.ensure_one()
        if not self.zvy_purchase_request_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'zvy.purchase.request',
            'res_id': self.zvy_purchase_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
