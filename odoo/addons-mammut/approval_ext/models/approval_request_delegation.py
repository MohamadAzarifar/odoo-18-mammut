# -*- coding: utf-8 -*-

from odoo import fields, models


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    def _approval_ext_apply_delegation_to_approvers(self):
        """Add substitute approvers for employees with active delegation (submit only)."""
        self.ensure_one()
        Delegation = self.env['hr.employee.approval.delegation']
        today = fields.Date.context_today(self)
        approvers = self.approver_ids.filtered(lambda a: a.status == 'new')

        for approver in approvers:
            delegate = Delegation._approval_ext_find_delegate_user(approver.user_id, today)
            if not delegate or delegate == approver.user_id:
                continue

            was_required = approver.required
            if was_required:
                approver.sudo().required = False

            existing_delegate = self.approver_ids.filtered(
                lambda a: a.user_id == delegate
            )[:1]
            if existing_delegate:
                if was_required and not existing_delegate.required:
                    existing_delegate.sudo().required = True
            else:
                self.env['approval.approver'].sudo().create({
                    'request_id': self.id,
                    'user_id': delegate.id,
                    'status': 'new',
                    'required': was_required,
                    'sequence': approver.sequence,
                })
