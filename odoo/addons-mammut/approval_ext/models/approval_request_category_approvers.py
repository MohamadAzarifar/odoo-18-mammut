# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    approval_ext_effective_minimum = fields.Integer(
        string='Effective approval minimum',
        compute='_compute_approval_ext_effective_minimum',
        store=True,
    )

    @api.depends(
        'category_id.approval_minimum',
        'category_id.approver_ids.user_id',
        'has_product',
        'product_line_ids.product_id',
        'product_line_ids.product_id.categ_id',
    )
    def _compute_approval_ext_effective_minimum(self):
        for request in self:
            base = request.category_id.approval_minimum or 0
            if request.has_product == 'no':
                request.approval_ext_effective_minimum = base
                continue
            base_user_ids = set(request.category_id.approver_ids.user_id.ids)
            product_users = request._approval_ext_product_category_approver_users()
            extra = product_users.filtered(lambda u: u.id not in base_user_ids)
            request.approval_ext_effective_minimum = base + len(extra)

    def _approval_ext_should_merge_product_category_approvers(self):
        self.ensure_one()
        if self.has_product == 'no':
            return False
        if self.request_status not in ('new', 'editing'):
            return False
        return True

    def _approval_ext_product_category_ids(self):
        self.ensure_one()
        return self.product_line_ids.product_id.categ_id

    def _approval_ext_product_category_approver_users(self):
        self.ensure_one()
        categories = self._approval_ext_product_category_ids()
        if not categories:
            return self.env['res.users']
        return categories.sudo().required_approver_user_ids.filtered(
            lambda u: u.active and not u.share
        )

    def _approval_ext_get_approver_commands(self):
        self.ensure_one()
        request = self
        users_to_category_approver = {
            approver.user_id.id: approver
            for approver in request.category_id.approver_ids
        }
        approver_id_vals = [Command.clear()]
        added_user_ids = set()

        if request.category_id.manager_approval:
            employee = self.env['hr.employee'].search([
                ('user_id', '=', request.request_owner_id.id),
                ('company_id', '=', request.company_id.id),
            ], limit=1)
            if employee.parent_id and employee.parent_id.user_id:
                manager_user_id = employee.parent_id.user_id.id
                manager_required = request.category_id.manager_approval == 'required'
                approver_id_vals.append(Command.create({
                    'user_id': manager_user_id,
                    'status': 'new',
                    'required': manager_required,
                    'sequence': 9,
                }))
                added_user_ids.add(manager_user_id)
                users_to_category_approver.pop(manager_user_id, None)

        for user_id, category_approver in users_to_category_approver.items():
            added_user_ids.add(user_id)
            approver_id_vals.append(Command.create({
                'user_id': user_id,
                'status': 'new',
                'required': category_approver.required,
                'sequence': category_approver.sequence,
            }))

        if request._approval_ext_should_merge_product_category_approvers():
            for user in request._approval_ext_product_category_approver_users():
                if user.id in added_user_ids:
                    continue
                added_user_ids.add(user.id)
                approver_id_vals.append(Command.create({
                    'user_id': user.id,
                    'status': 'new',
                    'required': True,
                    'sequence': 50,
                }))

        return approver_id_vals

    @api.depends(
        'category_id',
        'request_owner_id',
        'product_line_ids.product_id',
        'product_line_ids.product_id.categ_id',
    )
    def _compute_approver_ids(self):
        for request in self:
            commands = request._approval_ext_get_approver_commands()
            target = request.sudo() if request.request_owner_id == self.env.user else request
            target.update({'approver_ids': commands})

    def action_confirm(self):
        for request in self:
            request._approval_ext_apply_delegation_to_approvers()
            if request.has_product != 'no' and request.product_line_ids:
                effective = request.approval_ext_effective_minimum
                if len(request.approver_ids) < effective:
                    raise UserError(_(
                        'You need at least %(minimum)s approvers to confirm this request '
                        '(including approvers required for selected product categories).',
                        minimum=effective,
                    ))
        return super().action_confirm()

    @api.depends(
        'approver_ids.status',
        'approver_ids.required',
        'approval_ext_effective_minimum',
        'approval_ext_in_editing',
    )
    def _compute_request_status(self):
        super()._compute_request_status()
        for request in self:
            if request.approval_ext_in_editing:
                continue
            status_lst = request.mapped('approver_ids.status')
            if not status_lst:
                continue
            if status_lst.count('cancel') or status_lst.count('refused') or status_lst.count('new'):
                continue
            required_approved = all(
                a.status == 'approved'
                for a in request.approver_ids.filtered('required')
            )
            effective_min = request.approval_ext_effective_minimum
            minimal_approver = (
                effective_min if len(status_lst) >= effective_min else len(status_lst)
            )
            if status_lst.count('approved') >= minimal_approver and required_approved:
                request.request_status = 'approved'
            elif request.request_status == 'approved':
                request.request_status = 'pending'