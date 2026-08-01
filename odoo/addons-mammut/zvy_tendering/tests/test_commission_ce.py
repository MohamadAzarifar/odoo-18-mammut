# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyCommissionCe(ZvyTenderingCommon):

    def _route_to_commission(self):
        self.company_a.zvy_high_value_threshold = 1.0
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'commission')
        self.assertTrue(pr.commission_case_id)
        return pr, pr.commission_case_id

    def test_approve_without_meeting_when_all_approve(self):
        pr, case = self._route_to_commission()
        case = case.with_user(self.user_comm_mgr)
        case.write({'expert_user_ids': [(6, 0, [self.user_comm_exp.id])]})
        case.action_assign_experts()
        self.assertEqual(case.state, 'in_review')
        review = case.review_ids[0]
        review.with_user(self.user_comm_exp).write({
            'recommendation': 'approve',
            'notes_accuracy': 'ok',
            'notes_policy': 'ok',
            'notes_suppliers': 'ok',
        })
        review.with_user(self.user_comm_exp).action_submit()
        case.action_approve_without_meeting()
        self.assertEqual(case.state, 'approved')
        self.assertEqual(pr.state, 'signatory')
        self.assertTrue(pr.sudo().approval_request_id)

    def test_approve_without_meeting_blocked_if_not_all_approve(self):
        pr, case = self._route_to_commission()
        case = case.with_user(self.user_comm_mgr)
        case.write({'expert_user_ids': [(6, 0, [self.user_comm_exp.id])]})
        case.action_assign_experts()
        review = case.review_ids[0]
        review.with_user(self.user_comm_exp).write({
            'recommendation': 'request_corrections',
        })
        review.with_user(self.user_comm_exp).action_submit()
        with self.assertRaises(UserError):
            case.action_approve_without_meeting()
        self.assertEqual(pr.state, 'commission')

    def test_corrections_returns_to_quote_review(self):
        pr, case = self._route_to_commission()
        case = case.with_user(self.user_comm_mgr)
        case.write({'expert_user_ids': [(6, 0, [self.user_comm_exp.id])]})
        case.action_assign_experts()
        case.action_manager_corrections()
        self.assertEqual(case.state, 'corrections')
        self.assertEqual(pr.state, 'quote_review')

    def _create_ce_pending(self):
        pr = self._submit_and_assign()
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
        envelope.with_user(self.user_comm_mgr).write({
            'winner_partner_id': self.partner_a.id,
        })
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

        envelope.with_user(self.user_comm_mgr).write({
            'winner_partner_id': self.partner_a.id,
        })
        envelope.with_user(self.user_comm_mgr).action_select_winner()
        self.assertEqual(envelope.state, 'awarded')
        self.assertEqual(pr.award_partner_id, self.partner_a)
        self.assertEqual(pr.state, 'quote_review')
