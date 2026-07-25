# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"


    def _group_payment_request_approver_domain(self):
        group = self.env.ref("artarad_payment_request_base.group_artarad_payment_request_approver", raise_if_not_found=False)
        return [("groups_id", "in", group.ids)] if group else []
    
    payment_request_manager_id = fields.Many2one(
        "res.users", string="Payment Request",
        domain=_group_payment_request_approver_domain,
        compute="_compute_payment_request_manager", store=True, readonly=False,
        help="Select the user responsible for approving 'Payment Requests' of this employee.\n"
             "If empty, the approval is done by an Administrator or Approver (determined in settings/users).")

    @api.depends("parent_id")
    def _compute_payment_request_manager(self):
        for employee in self:
            previous_manager = employee._origin.parent_id.user_id
            manager = employee.parent_id.user_id
            if manager and manager.has_group("artarad_payment_request_base.group_artarad_payment_request_approver") and (employee.payment_request_manager_id == previous_manager or not employee.payment_request_manager_id):
                employee.payment_request_manager_id = manager
            elif not employee.payment_request_manager_id:
                employee.payment_request_manager_id = False

    payment_request_parent_ids = fields.Many2many("hr.employee", "hr_employee_payment_request_parent_rel", "hr_employee_id", "parent_id", string="Payment Request Parents", compute="_compute_payment_request_parent_ids", help="Direct and indirect payment request parents",
                                      compute_sudo=True, store=True)
    
    @api.depends("payment_request_manager_id")
    def _compute_payment_request_parent_ids(self):
        for employee in self:
            current_employee = employee
            while current_employee.payment_request_manager_id.employee_id and current_employee.payment_request_manager_id.employee_id != current_employee:
                employee.payment_request_parent_ids |= current_employee.payment_request_manager_id.employee_id
                current_employee = current_employee.payment_request_manager_id.employee_id


class EmployeePublic(models.Model):
    _inherit = "hr.employee.public"


    payment_request_manager_id = fields.Many2one("res.users", readonly=True)
    payment_request_parent_ids = fields.Many2many("hr.employee.public", "hr_employee_public_payment_request_parent_rel", "hr_employee_id", "parent_id", string="Payment Request Parents", compute="_compute_payment_request_parent_ids", help="Direct and indirect payment request parents",
                                      compute_sudo=True, store=True)


class User(models.Model):
    _inherit = ["res.users"]


    payment_request_manager_id = fields.Many2one(related="employee_id.payment_request_manager_id", readonly=False)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["payment_request_manager_id"]