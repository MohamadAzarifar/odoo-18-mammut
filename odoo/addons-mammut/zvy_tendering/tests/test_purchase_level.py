# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import ZvyTenderingCommon
from odoo.addons.zvy_tendering.models.zvy_purchase_bands import ZVY_PURCHASE_BANDS


@tagged('post_install', '-at_install')
class TestZvyPurchaseLevel(ZvyTenderingCommon):

    def test_bands_from_scale_and_nature(self):
        self.company_a.zvy_use_custom_bands = False
        self.company_a.zvy_company_scale = 'small'
        pr = self._create_draft_pr(line_vals=[{
            'product_id': self.product.id,
            'product_uom_qty': 1.0,
            'product_uom_id': self.product.uom_id.id,
            'price_estimate': 1_000_000_000,
        }])
        self.assertEqual(pr.purchase_nature, 'operational')
        self.assertEqual(pr.purchase_level, 'minor')

        pr.write({'purchase_nature': 'non_operational'})
        self.assertEqual(pr.purchase_level, 'medium')

        pr.write({'purchase_nature': 'operational'})
        pr.line_ids.write({'price_estimate': 2_000_000_000})
        self.assertEqual(pr.purchase_level, 'medium')

        self.company_a.zvy_company_scale = 'large'
        pr.invalidate_recordset(['purchase_level'])
        self.assertEqual(pr.purchase_level, 'minor')

    def test_baked_in_small_operational_ceilings(self):
        self.company_a.zvy_use_custom_bands = False
        self.company_a.zvy_company_scale = 'small'
        row = ZVY_PURCHASE_BANDS['small']['operational']
        self.assertEqual(
            self.company_a._zvy_band_ceilings('operational')['major_max'],
            row[2],
        )

    def test_custom_bands_minor_medium_major_large(self):
        self.company_a.write({
            'zvy_use_custom_bands': True,
            'zvy_op_minor_max': 100.0,
            'zvy_op_medium_max': 200.0,
            'zvy_op_major_max': 300.0,
            'zvy_op_large_ceo_max': 400.0,
        })
        cases = [
            (100.0, 'minor'),
            (150.0, 'medium'),
            (250.0, 'major'),
            (350.0, 'large'),
        ]
        for amount, level in cases:
            pr = self._create_draft_pr(line_vals=[{
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': amount,
            }])
            self.assertEqual(pr.purchase_level, level, amount)
            self.assertEqual(pr.is_high_value, level == 'large')

    def test_unpriced_and_stale_quote_not_valid(self):
        pr = self._submit_and_assign()
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        line = pr.line_ids[0]
        priced = Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_a.id,
            'price_unit': 10.0,
        })
        unpriced = Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_b.id,
            'price_unit': 0.0,
        })
        stale = Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_c.id,
            'price_unit': 12.0,
        })
        stale.sudo().write({
            'received_date': fields.Datetime.now() - timedelta(days=31),
        })
        self.assertTrue(priced.is_valid_inquiry)
        self.assertFalse(unpriced.is_valid_inquiry)
        self.assertFalse(stale.is_valid_inquiry)
        self.assertEqual(line._valid_inquiry_count(), 1)
        self.assertTrue(pr.is_formalities)

    def test_two_valid_inquiries_set_header_formalities(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr, count=2)
        pr.line_ids.sudo().write({
            'quote_shortfall_reason': 'Only two vendors responded',
        })
        pr.with_user(self.user_cce).action_submit_quotes()
        self.assertTrue(pr.is_formalities)
        self.assertEqual(pr.line_ids._valid_inquiry_count(), 2)

    def test_three_valid_inquiries_clears_formalities(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr, count=3)
        pr.with_user(self.user_cce).action_submit_quotes()
        self.assertFalse(pr.is_formalities)

    def test_tendering_pr_is_not_formalities(self):
        pr = self._create_draft_pr(line_vals=[{
            'product_id': self.product_tendering.id,
            'product_uom_qty': 1.0,
            'product_uom_id': self.product_tendering.uom_id.id,
            'price_estimate': 50.0,
        }])
        self.assertEqual(pr.procurement_type, 'tendering')
        self.assertFalse(pr.is_formalities)

    def test_formalities_appends_extra_approvers(self):
        self.company_a.zvy_signatory_formalities_ids = [(6, 0, [self.user_signatory_other.id])]
        pr = self._submit_and_assign()
        self._add_quotes(pr, count=2)
        pr.line_ids.sudo().write({
            'quote_shortfall_reason': 'Only two vendors responded',
        })
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        self.assertTrue(pr.is_formalities)
        users = pr.sudo().approval_request_id.approver_ids.mapped('user_id')
        self.assertIn(self.user_signatory, users)
        self.assertIn(self.user_signatory_other, users)

        standard = self._submit_and_assign()
        self._add_quotes(standard, count=3)
        standard.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(standard)
        standard.with_user(self.user_cm).action_approve_quotes()
        self.assertFalse(standard.is_formalities)
        std_users = standard.sudo().approval_request_id.approver_ids.mapped('user_id')
        self.assertIn(self.user_signatory, std_users)
        self.assertNotIn(self.user_signatory_other, std_users)

    def test_large_above_inner_ceiling_uses_board(self):
        self.company_a.write({
            'zvy_use_custom_bands': True,
            'zvy_op_minor_max': 10.0,
            'zvy_op_medium_max': 20.0,
            'zvy_op_major_max': 30.0,
            'zvy_op_large_ceo_max': 40.0,
        })
        pr = self._create_draft_pr(line_vals=[{
            'product_id': self.product.id,
            'product_uom_qty': 1.0,
            'product_uom_id': self.product.uom_id.id,
            'price_estimate': 50.0,
        }])
        pr = self._submit_and_assign(pr=pr)
        self.assertEqual(pr.purchase_level, 'large')
        quotes = self._add_quotes(pr, count=3)
        quotes[0].sudo().write({'price_unit': 50.0})
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        # Awarded total 50*2 default qty? qty is 1, first quote 50 → 50
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'commission')
        case = pr.commission_case_id.with_user(self.user_comm_mgr)
        case._action_assign_experts([self.user_comm_exp.id])
        review = case.review_ids[0]
        review.with_user(self.user_comm_exp).write({
            'recommendation': 'approve',
            'notes_accuracy': 'ok',
            'notes_policy': 'ok',
            'notes_suppliers': 'ok',
        })
        review.with_user(self.user_comm_exp).action_submit()
        case.action_approve_without_meeting()
        self.assertEqual(pr.state, 'signatory')
        users = pr.sudo().approval_request_id.approver_ids.mapped('user_id')
        self.assertIn(self.user_signatory_other, users)
        self.assertNotIn(self.user_signatory, users)

    def test_effective_qty_change_resets_chain(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr, count=3)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        old = pr.sudo().approval_request_id
        self.assertEqual(old.request_status, 'pending')

        pr.line_ids.with_user(self.user_cm).write({'product_uom_qty': 5.0})
        pr.invalidate_recordset()
        new = pr.sudo().approval_request_id
        self.assertNotEqual(new, old)
        self.assertEqual(old.request_status, 'cancel')
        self.assertEqual(old.zvy_purchase_request_id, pr)
        self.assertEqual(new.request_status, 'pending')
        self.assertGreaterEqual(pr.approval_request_count, 2)

        # Stale cancelled approval must not push the PR to po_ready.
        self.assertEqual(pr.state, 'signatory')
        self._approve_all_signatories(pr)
        self.assertEqual(pr.state, 'po_ready')
        self.assertEqual(pr.sudo().approval_request_id, new)
