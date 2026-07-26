# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyPurchaseRequestIntake(ZvyTenderingCommon):

    def test_submit_moves_to_cm_queue_with_sequence(self):
        pr = self._create_draft_pr()
        self.assertNotEqual(pr.name, 'New')
        self.assertTrue(pr.name.startswith('PR/'))
        self.assertEqual(pr.state, 'draft')
        self.assertEqual(pr.amount_total, 100.0)

        pr.action_submit()
        self.assertEqual(pr.state, 'submitted')

    def test_reject_requires_reason_and_notifies_planner(self):
        pr = self._create_draft_pr()
        pr.action_submit()

        with self.assertRaises(ValidationError):
            pr.with_user(self.user_cm)._action_reject('   ')

        activities_before = self.env['mail.activity'].search_count([
            ('res_model', '=', 'zvy.purchase.request'),
            ('res_id', '=', pr.id),
            ('user_id', '=', self.user_planner.id),
        ])
        pr.with_user(self.user_cm)._action_reject('Incomplete specifications')
        self.assertEqual(pr.state, 'rejected')
        self.assertEqual(pr.reject_reason, 'Incomplete specifications')

        activities_after = self.env['mail.activity'].search_count([
            ('res_model', '=', 'zvy.purchase.request'),
            ('res_id', '=', pr.id),
            ('user_id', '=', self.user_planner.id),
        ])
        self.assertGreater(activities_after, activities_before)

    def test_return_correction_and_resubmit(self):
        pr = self._create_draft_pr()
        pr.action_submit()
        pr.with_user(self.user_cm)._action_return_correction('Missing quantity')
        self.assertEqual(pr.state, 'correction')
        self.assertEqual(pr.return_reason, 'Missing quantity')

        pr.with_user(self.user_planner).write({
            'description': 'Updated description',
        })
        pr.with_user(self.user_planner).action_submit()
        self.assertEqual(pr.state, 'submitted')

    def test_planner_rpc_create_and_submit(self):
        """FR-1: create + action_submit as planner (XML/JSON-RPC equivalent)."""
        Request = self.env['zvy.purchase.request'].with_user(self.user_planner).with_company(
            self.company_a
        )
        pr = Request.create({
            'company_id': self.company_a.id,
            'requester_id': self.user_planner.id,
            'description': 'RPC PR',
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_estimate': 25.0,
            })],
        })
        self.assertEqual(pr.state, 'draft')
        pr.action_submit()
        self.assertEqual(pr.state, 'submitted')

        with self.assertRaises(AccessError):
            self.env['zvy.purchase.request'].with_user(self.user_cm).with_company(
                self.company_a
            ).create({
                'company_id': self.company_a.id,
                'requester_id': self.user_cm.id,
                'description': 'CM cannot create',
                'line_ids': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1.0,
                    'price_estimate': 10.0,
                })],
            })

    def test_planner_own_record_rule_and_cm_sees_all(self):
        pr_mine = self._create_draft_pr(user=self.user_planner)
        pr_other = self._create_draft_pr(user=self.user_planner_other)

        PlannerRequest = self.env['zvy.purchase.request'].with_user(self.user_planner)
        visible = PlannerRequest.search([])
        self.assertIn(pr_mine, visible)
        self.assertNotIn(pr_other, visible)

        CmRequest = self.env['zvy.purchase.request'].with_user(self.user_cm)
        cm_visible = CmRequest.search([])
        self.assertIn(pr_mine, cm_visible)
        self.assertIn(pr_other, cm_visible)

    def test_submit_without_lines_fails(self):
        pr = self.env['zvy.purchase.request'].with_user(self.user_planner).create({
            'company_id': self.company_a.id,
            'requester_id': self.user_planner.id,
            'description': 'Empty PR',
        })
        with self.assertRaises(ValidationError):
            pr.action_submit()

    def test_cannot_edit_submitted_content(self):
        pr = self._create_draft_pr()
        pr.action_submit()
        with self.assertRaises(UserError):
            pr.with_user(self.user_planner).write({'description': 'Tamper'})
