# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
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
            'zvy_signatory_minor_job_id': self.job_signatory.id,
            'zvy_default_bid_window_hours': 48,
            'zvy_signatory_approval_category_id': category.id,
        })
        settings.execute()
        company = self.company_a
        self.assertEqual(company.zvy_high_value_threshold, 50000.0)
        self.assertEqual(company.zvy_company_scale, 'medium')
        self.assertEqual(company.zvy_signatory_minor_job_id, self.job_signatory)
        self.assertEqual(company.zvy_default_bid_window_hours, 48)
        self.assertEqual(company.zvy_signatory_approval_category_id, category)

        reread = Settings.create({'company_id': self.company_a.id})
        self.assertEqual(reread.zvy_high_value_threshold, 50000.0)
        self.assertEqual(reread.zvy_company_scale, 'medium')
        self.assertEqual(reread.zvy_signatory_minor_job_id, self.job_signatory)
        self.assertEqual(reread.zvy_default_bid_window_hours, 48)
        self.assertEqual(reread.zvy_signatory_approval_category_id, category)

    def test_signatory_job_expands_all_employees(self):
        self.employee_signatory_other.job_id = self.job_signatory
        users = self.company_a._zvy_users_from_job(self.job_signatory)
        self.assertEqual(set(users.ids), {
            self.user_signatory.id,
            self.user_signatory_other.id,
        })
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        approvers = pr.sudo().approval_request_id.approver_ids.sorted(
            lambda a: (a.sequence, a.id)
        )
        self.assertEqual(len(approvers), 2)
        self.assertTrue(all(a.required for a in approvers))
        self.assertEqual(approvers.mapped('user_id').ids, users.ids)

    def test_avl_active_filter_in_partner_domain(self):
        domain = self.Avl._avl_partner_domain()
        partners = self.env['res.partner'].search(domain)
        self.assertIn(self.partner_a, partners)

        self.avl_a.active = False
        domain = self.Avl._avl_partner_domain()
        partners = self.env['res.partner'].search(domain)
        self.assertNotIn(self.partner_a, partners)

    def test_avl_is_global(self):
        Avl = self.env['zvy.avl.entry'].with_user(self.user_company_a)
        visible = Avl.search([])
        self.assertIn(self.avl_a, visible)
        self.assertIn(self.avl_b, visible)
        self.assertIn(self.avl_a3, visible)

    def test_product_procurement_type_defaults(self):
        self.assertEqual(self.product.zvy_procurement_type, 'enquiry')
        self.assertFalse(self.product.zvy_need_commission)

    def test_product_menu_admin_only(self):
        menu = self.env.ref('zvy_tendering.menu_zvy_product_template')
        self.assertIn(self.group_admin, menu.groups_id)
        self.assertNotIn(self.group_planner, menu.groups_id)
        self.assertNotIn(self.group_cm, menu.groups_id)
        self.assertNotIn(self.group_cce, menu.groups_id)
        action = self.env.ref('zvy_tendering.action_zvy_product_template')
        self.assertEqual(menu.action, action)

        created = self.env['product.template'].with_user(self.user_company_a).create({
            'name': 'Admin Created Product',
            'type': 'consu',
        })
        self.assertEqual(created.zvy_procurement_type, 'enquiry')

        with self.assertRaises(AccessError):
            self.env['product.template'].with_user(self.user_planner).create({
                'name': 'Planner Created Product',
                'type': 'consu',
            })

