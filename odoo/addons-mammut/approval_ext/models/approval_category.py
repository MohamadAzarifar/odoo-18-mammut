# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.osv import expression


class ApprovalCategory(models.Model):
    _inherit = 'approval.category'

    approval_ext_product_category_ids = fields.Many2many(
        comodel_name='product.category',
        relation='approval_category_product_category_rel',
        column1='approval_category_id',
        column2='product_category_id',
        string='Product Categories',
        help=(
            'When set, approval requests of this type only allow products in '
            'these categories (including subcategories). Leave empty to allow all products.'
        ),
    )
    department_ids = fields.Many2many(
        comodel_name='hr.department',
        relation='approval_category_department_rel',
        column1='approval_category_id',
        column2='department_id',
        string='Department access',
        check_company=True,
        help=(
            'When empty, all internal users may start requests of this type. '
            'When set, an employee sees this type if their department is the '
            'configured department or a parent of it (e.g. IT sees types for '
            'IT/Helpdesk). Sub-departments do not see types assigned only to '
            'a parent department.'
        ),
    )

    @api.model
    def _approval_ext_should_filter_departments_for_user(self, user=None):
        """Filter type pickers for internal users without Approval User / Admin groups."""
        user = user or self.env.user
        if not user or user._is_public():
            return False
        return (
            not user.has_group('approvals.group_approval_user')
            and not user.has_group('approvals.group_approval_manager')
        )

    @api.model
    def _approval_ext_get_user_employee(self, user=None):
        user = user or self.env.user
        return self.env['hr.employee'].search([
            ('user_id', '=', user.id),
            ('company_id', 'in', self.env.companies.ids),
        ], limit=1)

    @api.model
    def _approval_ext_department_selection_domain(self, user=None):
        """Domain for type pickers (kanban, many2one, Search More).

        Parent department employees see types assigned to that department or
        any sub-department. Sub-department employees only see types assigned to
        their branch (not types assigned only to a parent).
        """
        if not self._approval_ext_should_filter_departments_for_user(user):
            return []
        employee = self._approval_ext_get_user_employee(user)
        if not employee.department_id:
            return [('department_ids', '=', False)]
        subtree_ids = self.env['hr.department'].search([
            ('id', 'child_of', employee.department_id.id),
        ]).ids
        return [
            '|',
            ('department_ids', '=', False),
            ('department_ids', 'in', subtree_ids),
        ]

    def _approval_ext_is_selectable_for_user(self, user=None):
        """Whether the user may pick this type when creating a request."""
        self.ensure_one()
        user = user or self.env.user
        if not self._approval_ext_should_filter_departments_for_user(user):
            return True
        domain = self.env['approval.category']._approval_ext_department_selection_domain(user)
        return bool(self.filtered_domain(domain))

    @api.model
    def _approval_ext_is_point_id_lookup(self, domain):
        """True when search only resolves explicit ids (ORM many2one existence check).

        Those lookups must not apply the department picker filter, otherwise
        assigning or displaying an existing ``category_id`` raises AccessError.
        """
        domain = expression.normalize_domain(domain or [])
        if not domain:
            return False
        for token in domain:
            if token in ('&', '|', '!'):
                continue
            if not (isinstance(token, (list, tuple)) and len(token) == 3):
                return False
            if token[0] != 'id':
                return False
        return True

    @api.model
    def _approval_ext_merge_department_selection_domain(self, domain):
        """Apply department visibility for employees on open searches/pickers."""
        if not self._approval_ext_should_filter_departments_for_user():
            return domain
        extra = self._approval_ext_department_selection_domain()
        if extra:
            return expression.AND([domain or [], extra])
        return domain

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if not self._approval_ext_is_point_id_lookup(domain):
            domain = self._approval_ext_merge_department_selection_domain(domain)
        return super()._search(domain, offset=offset, limit=limit, order=order)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = self._approval_ext_merge_department_selection_domain(args or [])
        return super().name_search(name, args, operator, limit)
