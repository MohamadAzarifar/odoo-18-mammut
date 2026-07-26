# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class ZvyTenderingCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env['res.company'].create({'name': 'ZVY Company A'})
        cls.company_b = cls.env['res.company'].create({'name': 'ZVY Company B'})
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'AVL Vendor A',
            'supplier_rank': 1,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'AVL Vendor B',
            'supplier_rank': 1,
        })
        cls.partner_c = cls.env['res.partner'].create({
            'name': 'AVL Vendor C',
            'supplier_rank': 1,
        })
        cls.partner_non_avl = cls.env['res.partner'].create({
            'name': 'Non AVL Vendor',
            'supplier_rank': 1,
        })
        cls.Avl = cls.env['zvy.avl.entry']
        cls.avl_a = cls.Avl.create({
            'partner_id': cls.partner_a.id,
            'company_id': cls.company_a.id,
        })
        cls.avl_b = cls.Avl.create({
            'partner_id': cls.partner_b.id,
            'company_id': cls.company_b.id,
        })
        cls.avl_a2 = cls.Avl.create({
            'partner_id': cls.partner_b.id,
            'company_id': cls.company_a.id,
        })
        cls.avl_a3 = cls.Avl.create({
            'partner_id': cls.partner_c.id,
            'company_id': cls.company_a.id,
        })
        cls.group_admin = cls.env.ref('zvy_tendering.group_zvy_tendering_admin')
        cls.group_planner = cls.env.ref('zvy_tendering.group_zvy_planner')
        cls.group_cm = cls.env.ref('zvy_tendering.group_zvy_commercial_manager')
        cls.group_cce = cls.env.ref('zvy_tendering.group_zvy_commercial_expert')
        cls.user_company_a = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Admin Company A',
            'login': 'zvy_admin_company_a',
            'email': 'zvy_admin_a@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_admin.id,
            ])],
        })
        cls.product = cls.env['product.product'].create({
            'name': 'ZVY Test Product',
            'type': 'consu',
            'list_price': 100.0,
        })
        cls.commission_categ = cls.env['product.category'].create({
            'name': 'ZVY Commission Category',
            'zvy_is_commission_item': True,
        })
        cls.product_commission = cls.env['product.product'].create({
            'name': 'ZVY Commission Product',
            'type': 'consu',
            'list_price': 50.0,
            'categ_id': cls.commission_categ.id,
        })
        cls.user_planner = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Planner',
            'login': 'zvy_planner',
            'email': 'zvy_planner@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_planner.id,
            ])],
        })
        cls.user_planner_other = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Planner Other',
            'login': 'zvy_planner_other',
            'email': 'zvy_planner_other@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_planner.id,
            ])],
        })
        cls.user_cm = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Commercial Manager',
            'login': 'zvy_cm',
            'email': 'zvy_cm@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_cm.id,
            ])],
        })
        cls.user_cce = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Commercial Expert',
            'login': 'zvy_cce',
            'email': 'zvy_cce@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_cce.id,
            ])],
        })
        cls.user_cce_other = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Commercial Expert Other',
            'login': 'zvy_cce_other',
            'email': 'zvy_cce_other@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_cce.id,
            ])],
        })

    def _create_draft_pr(self, user=None, company=None, **extra):
        user = user or self.user_planner
        company = company or self.company_a
        line_vals = extra.pop('line_vals', None)
        if line_vals is None:
            line_vals = [{
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 50.0,
            }]
        vals = {
            'company_id': company.id,
            'requester_id': user.id,
            'description': extra.pop('description', 'Test PR'),
            'line_ids': [(0, 0, line) for line in line_vals],
        }
        vals.update(extra)
        return self.env['zvy.purchase.request'].with_user(user).with_company(company).create(vals)

    def _submit_and_assign(self, pr=None, experts=None):
        """Create (optional), submit, and assign experts → inquiry."""
        pr = pr or self._create_draft_pr()
        if pr.state == 'draft':
            pr.action_submit()
        experts = experts or self.user_cce
        if hasattr(experts, 'ids'):
            expert_ids = experts.ids
        else:
            expert_ids = [experts.id]
        assignments = {line.id: expert_ids for line in pr.line_ids}
        pr.with_user(self.user_cm)._action_assign_experts(assignments)
        return pr

    def _add_quotes(self, pr, count=3, user=None, partners=None):
        """Add `count` AVL quotes on the first line (or all lines if sole source uses 1)."""
        user = user or self.user_cce
        partners = partners or [self.partner_a, self.partner_b, self.partner_c]
        Quote = self.env['zvy.quote'].with_user(user).with_company(pr.company_id)
        quotes = self.env['zvy.quote']
        for line in pr.line_ids:
            needed = 1 if line.sole_source else count
            for i in range(needed):
                partner = partners[i % len(partners)]
                quotes |= Quote.create({
                    'line_id': line.id,
                    'request_id': pr.id,
                    'partner_id': partner.id,
                    'price_unit': 10.0 + i,
                })
        return quotes
