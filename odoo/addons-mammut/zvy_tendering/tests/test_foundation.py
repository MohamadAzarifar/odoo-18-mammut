# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyTenderingFoundation(ZvyTenderingCommon):

    def test_settings_write_read_on_company(self):
        category = self.env['approval.category'].with_company(self.company_a).create({
            'name': 'ZVY Signatory Chain',
            'company_id': self.company_a.id,
        })
        Settings = self.env['res.config.settings'].with_company(self.company_a)
        settings = Settings.create({
            'company_id': self.company_a.id,
            'zvy_high_value_threshold': 50000.0,
            'zvy_company_scale': 'medium',
            'zvy_signatory_minor_ids': [(6, 0, [self.user_signatory.id])],
            'zvy_default_bid_window_hours': 48,
            'zvy_signatory_approval_category_id': category.id,
            'zvy_sole_source_approver_ids': [(6, 0, [self.user_ceo.id])],
        })
        settings.execute()
        company = self.company_a
        self.assertEqual(company.zvy_high_value_threshold, 50000.0)
        self.assertEqual(company.zvy_company_scale, 'medium')
        self.assertIn(self.user_signatory, company.zvy_signatory_minor_ids)
        self.assertEqual(company.zvy_default_bid_window_hours, 48)
        self.assertEqual(company.zvy_signatory_approval_category_id, category)
        self.assertIn(self.user_ceo, company.zvy_sole_source_approver_ids)

        reread = Settings.create({'company_id': self.company_a.id})
        self.assertEqual(reread.zvy_high_value_threshold, 50000.0)
        self.assertEqual(reread.zvy_company_scale, 'medium')
        self.assertIn(self.user_signatory, reread.zvy_signatory_minor_ids)
        self.assertEqual(reread.zvy_default_bid_window_hours, 48)
        self.assertEqual(reread.zvy_signatory_approval_category_id, category)
        self.assertIn(self.user_ceo, reread.zvy_sole_source_approver_ids)

    def test_avl_active_filter_in_partner_domain(self):
        domain = self.Avl._avl_partner_domain(self.company_a)
        partners = self.env['res.partner'].search(domain)
        self.assertIn(self.partner_a, partners)

        self.avl_a.active = False
        domain = self.Avl._avl_partner_domain(self.company_a)
        partners = self.env['res.partner'].search(domain)
        self.assertNotIn(self.partner_a, partners)

    def test_avl_multi_company_isolation(self):
        Avl = self.env['zvy.avl.entry'].with_user(self.user_company_a)
        visible = Avl.search([])
        self.assertIn(self.avl_a, visible)
        self.assertNotIn(self.avl_b, visible)
        # Record rules apply on search/read; exists() checks the DB row only.
        self.assertFalse(Avl.search([('id', '=', self.avl_b.id)]))

    def test_product_procurement_type_defaults(self):
        self.assertEqual(self.product.zvy_procurement_type, 'enquiry')
        self.assertFalse(self.product.zvy_need_commission)

