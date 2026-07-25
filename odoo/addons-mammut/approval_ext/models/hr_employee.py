# -*- coding: utf-8 -*-

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    approval_delegation_ids = fields.One2many(
        comodel_name='hr.employee.approval.delegation',
        inverse_name='employee_id',
        string='Approval delegations',
    )
