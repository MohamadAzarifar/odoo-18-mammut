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
