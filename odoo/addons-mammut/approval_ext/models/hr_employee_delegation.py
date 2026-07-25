# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployeeApprovalDelegation(models.Model):
    _name = 'hr.employee.approval.delegation'
    _description = 'Employee Approval Delegation'
    _order = 'start_date desc, id desc'

    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Delegate',
        required=True,
        domain="[('share', '=', False)]",
        help='User who approves on behalf of the employee during this period.',
    )
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    company_id = fields.Many2one(
        related='employee_id.company_id',
        store=True,
        readonly=True,
    )

    @api.model
    def _approval_ext_find_delegate_user(self, user, on_date=None):
        """Return the substitute approver for user on on_date, or empty recordset."""
        on_date = on_date or fields.Date.context_today(self)
        if not user:
            return self.env['res.users']
        employee = self.env['hr.employee'].search([
            ('user_id', '=', user.id),
            ('company_id', 'in', self.env.companies.ids),
        ], limit=1)
        if not employee:
            return self.env['res.users']
        line = self.search([
            ('employee_id', '=', employee.id),
            ('start_date', '<=', on_date),
            ('end_date', '>=', on_date),
        ], limit=1)
        return line.user_id if line else self.env['res.users']

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for line in self:
            if line.start_date and line.end_date and line.start_date > line.end_date:
                raise ValidationError(_(
                    'Delegation start date must be on or before the end date.'
                ))

    @api.constrains('employee_id', 'user_id', 'start_date', 'end_date')
    def _check_delegation_rules(self):
        for line in self.filtered(lambda l: l.start_date and l.end_date):
            employee_user = line.employee_id.user_id
            if employee_user and line.user_id == employee_user:
                raise ValidationError(_(
                    'The delegate must be different from the employee user.'
                ))
            if line.user_id.share:
                raise ValidationError(_(
                    'The delegate must be an internal user.'
                ))

            same_employee = self.search([
                ('id', '!=', line.id),
                ('employee_id', '=', line.employee_id.id),
                ('start_date', '<=', line.end_date),
                ('end_date', '>=', line.start_date),
            ])
            if same_employee:
                raise ValidationError(_(
                    'Delegation periods for the same employee cannot overlap.'
                ))

            other_delegate = self.search([
                ('id', '!=', line.id),
                ('user_id', '=', line.user_id.id),
                ('start_date', '<=', line.end_date),
                ('end_date', '>=', line.start_date),
            ])
            if other_delegate:
                raise ValidationError(_(
                    'User "%(user)s" is already assigned as delegate for another employee '
                    'in an overlapping period.',
                    user=line.user_id.display_name,
                ))

            delegate_employee = self.env['hr.employee'].search([
                ('user_id', '=', line.user_id.id),
                ('company_id', 'in', self.env.companies.ids),
            ], limit=1)
            if delegate_employee:
                outgoing = self.search([
                    ('employee_id', '=', delegate_employee.id),
                    ('start_date', '<=', line.end_date),
                    ('end_date', '>=', line.start_date),
                ])
                if outgoing:
                    raise ValidationError(_(
                        'User "%(user)s" has an active outgoing delegation in this period '
                        'and cannot act as a delegate.',
                        user=line.user_id.display_name,
                    ))
