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
        cls.Avl = cls.env['zvy.avl.entry']
        cls.avl_a = cls.Avl.create({
            'partner_id': cls.partner_a.id,
            'company_id': cls.company_a.id,
        })
        cls.avl_b = cls.Avl.create({
            'partner_id': cls.partner_b.id,
            'company_id': cls.company_b.id,
        })
        cls.group_admin = cls.env.ref('zvy_tendering.group_zvy_tendering_admin')
        cls.group_planner = cls.env.ref('zvy_tendering.group_zvy_planner')
        cls.group_cm = cls.env.ref('zvy_tendering.group_zvy_commercial_manager')
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

    def _create_draft_pr(self, user=None, company=None, **extra):
        user = user or self.user_planner
        company = company or self.company_a
        vals = {
            'company_id': company.id,
            'requester_id': user.id,
            'description': extra.pop('description', 'Test PR'),
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 50.0,
            })],
        }
        vals.update(extra)
        return self.env['zvy.purchase.request'].with_user(user).with_company(company).create(vals)
