# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyCommissionCe(ZvyTenderingCommon):

    def _route_to_commission(self):
        self._force_large_bands()
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        self._approve_all_signatories(pr, expected_state='commission')
        self.assertEqual(pr.state, 'commission')
        self.assertTrue(pr.commission_case_id)
        return pr, pr.commission_case_id

    def test_approve_without_meeting_when_all_approve(self):
        pr, case = self._route_to_commission()
        approval = pr.sudo().approval_request_id
        self.assertEqual(approval.request_status, 'approved')
        self._approve_commission_without_meeting(case)
        self.assertEqual(case.state, 'approved')
        self.assertEqual(pr.state, 'po_ready')
        self.assertEqual(pr.sudo().approval_request_id, approval)
        self.assertEqual(
            self.env['approval.request'].sudo().search_count([
                ('zvy_purchase_request_id', '=', pr.id),
            ]),
            1,
        )

    def test_approve_without_meeting_with_mixed_recommendation(self):
        pr, case = self._route_to_commission()
        case = case.with_user(self.user_comm_mgr)
        case._action_assign_experts([self.user_comm_exp.id])
        review = case.review_ids[0]
        review.with_user(self.user_comm_exp).write({
            'recommendation': 'request_corrections',
        })
        review.with_user(self.user_comm_exp).action_submit()
        case.action_approve_without_meeting()
        self.assertEqual(case.state, 'approved')
        self.assertEqual(pr.state, 'po_ready')

    def test_approve_without_meeting_from_open(self):
        _pr, case = self._route_to_commission()
        self.assertEqual(case.state, 'open')
        case.with_user(self.user_comm_mgr).action_approve_without_meeting()
        self.assertEqual(case.state, 'approved')
        self.assertEqual(_pr.state, 'po_ready')

    def test_corrections_returns_to_quote_review(self):
        pr, case = self._route_to_commission()
        case = case.with_user(self.user_comm_mgr)
        case._action_assign_experts([self.user_comm_exp.id])
        case.action_manager_corrections()
        self.assertEqual(case.state, 'corrections')
        self.assertEqual(pr.state, 'quote_review')

    def test_assign_experts_wizard(self):
        _pr, case = self._route_to_commission()
        case = case.with_user(self.user_comm_mgr)
        action = case.action_assign_experts()
        self.assertEqual(action['res_model'], 'zvy.commission.assign.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_case_id'], case.id)

        wizard = self.env['zvy.commission.assign.wizard'].with_user(
            self.user_comm_mgr
        ).create({'case_id': case.id})
        self.assertEqual(wizard.case_id, case)
        self.assertFalse(wizard.expert_user_ids)
        with self.assertRaises(ValidationError):
            wizard.action_confirm()

        wizard.write({'expert_user_ids': [(6, 0, [self.user_comm_exp.id])]})
        wizard.action_confirm()
        self.assertEqual(case.state, 'in_review')
        self.assertEqual(case.expert_user_ids, self.user_comm_exp)
        self.assertEqual(case.review_ids.expert_user_id, self.user_comm_exp)
        self.assertTrue(case.activity_ids.filtered(
            lambda a: a.user_id == self.user_comm_exp
        ))

    def _create_ce_pending(self):
        pr = self._submit_and_assign(pr=self._create_draft_pr(line_vals=[{
            'product_id': self.product_tendering.id,
            'product_uom_qty': 2.0,
            'product_uom_id': self.product_tendering.uom_id.id,
            'price_estimate': 50.0,
        }]))
        envelope = self.env['zvy.closed.envelope'].with_user(self.user_cce).with_company(
            self.company_a
        ).create({
            'request_id': pr.id,
            'invite_partner_ids': [(6, 0, [
                self.partner_a.id, self.partner_b.id, self.partner_c.id,
            ])],
        })
        envelope.with_user(self.user_cce).action_submit_list()
        self.assertEqual(envelope.state, 'list_pending')
        self.assertEqual(pr.closed_envelope_id, envelope)
        return pr, envelope

    def test_list_approval_without_opening_fails(self):
        _pr, envelope = self._create_ce_pending()
        with self.assertRaises(ValidationError):
            envelope.with_user(self.user_comm_mgr).action_approve_list()

    def test_list_approval_defaults_bid_deadline(self):
        self.company_a.zvy_default_bid_window_hours = 48
        _pr, envelope = self._create_ce_pending()
        opening = fields.Datetime.now() + timedelta(hours=1)
        envelope.with_user(self.user_comm_mgr).write({
            'opening_datetime': opening,
        })
        envelope.with_user(self.user_comm_mgr).action_approve_list()
        self.assertEqual(envelope.state, 'portal_open')
        self.assertTrue(envelope.bid_deadline)
        expected = fields.Datetime.to_datetime(opening) + timedelta(hours=48)
        self.assertEqual(envelope.bid_deadline, expected)

    def test_winner_selection_blocked_before_open(self):
        _pr, envelope = self._create_ce_pending()
        opening = fields.Datetime.now() - timedelta(hours=1)
        envelope.with_user(self.user_comm_mgr).write({
            'opening_datetime': opening,
            'bid_deadline': opening + timedelta(hours=24),
        })
        envelope.with_user(self.user_comm_mgr).action_approve_list()
        with self.assertRaises(UserError):
            envelope.with_user(self.user_comm_mgr).action_select_winner()

    def test_bid_seal_and_open_and_award(self):
        pr, envelope = self._create_ce_pending()
        opening = fields.Datetime.now() - timedelta(minutes=5)
        envelope.with_user(self.user_comm_mgr).write({
            'opening_datetime': opening,
            'bid_deadline': opening + timedelta(hours=24),
        })
        envelope.with_user(self.user_comm_mgr).action_approve_list()

        bid = self.env['zvy.closed.envelope.bid'].with_user(
            self.user_comm_mgr
        ).with_company(self.company_a).create({
            'envelope_id': envelope.id,
            'partner_id': self.partner_a.id,
            'amount': 1234.5,
            'notes': 'secret',
        })

        sealed = bid.with_user(self.user_cce).read(['amount', 'notes'])[0]
        self.assertEqual(sealed['amount'], 0.0)
        self.assertFalse(sealed['notes'])

        manager_read = bid.with_user(self.user_comm_mgr).read(['amount', 'notes'])[0]
        self.assertEqual(manager_read['amount'], 1234.5)
        self.assertEqual(manager_read['notes'], 'secret')

        own = bid.with_user(self.user_bidder).read(['amount', 'notes'])[0]
        self.assertEqual(own['amount'], 1234.5)

        envelope.with_user(self.user_comm_mgr).action_open_bids()
        self.assertEqual(envelope.state, 'opened')
        after_open = bid.with_user(self.user_cce).read(['amount'])[0]
        self.assertEqual(after_open['amount'], 1234.5)

        bid.line_ids.with_user(self.user_comm_mgr).write({'is_winner': True})
        envelope.with_user(self.user_comm_mgr).action_select_winner()
        self.assertEqual(envelope.state, 'awarded')
        self.assertEqual(pr.award_partner_id, self.partner_a)
        self.assertEqual(pr.state, 'quote_review')

    def test_tendering_high_value_commission_before_signatory(self):
        self._force_large_bands()
        pr, envelope = self._create_ce_pending()
        opening = fields.Datetime.now() - timedelta(minutes=5)
        envelope.with_user(self.user_comm_mgr).write({
            'opening_datetime': opening,
            'bid_deadline': opening + timedelta(hours=24),
        })
        envelope.with_user(self.user_comm_mgr).action_approve_list()
        self.env['zvy.closed.envelope.bid'].with_user(
            self.user_comm_mgr
        ).with_company(self.company_a).create({
            'envelope_id': envelope.id,
            'partner_id': self.partner_a.id,
            'amount': 1234.5,
        })
        envelope.with_user(self.user_comm_mgr).action_open_bids()
        bid = envelope.bid_ids.filtered(lambda b: b.partner_id == self.partner_a)
        bid.line_ids.with_user(self.user_comm_mgr).write({'is_winner': True})
        envelope.with_user(self.user_comm_mgr).action_select_winner()
        self.assertEqual(pr.state, 'quote_review')
        self.assertTrue(pr.is_high_value)
        self.assertFalse(pr.sudo().approval_request_id)

        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'commission')
        self.assertTrue(pr.commission_case_id)
        self.assertFalse(pr.sudo().approval_request_id)

        self._approve_commission_without_meeting(pr.commission_case_id)
        self.assertEqual(pr.state, 'signatory')
        self.assertTrue(pr.sudo().approval_request_id)
        self.assertEqual(pr.sudo().approval_request_id.request_status, 'pending')
