# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyPerItemBids(ZvyTenderingCommon):

    def _tendering_line_vals(self, qty=2.0, estimate=50.0):
        return {
            'product_id': self.product_tendering.id,
            'product_uom_qty': qty,
            'product_uom_id': self.product_tendering.uom_id.id,
            'price_estimate': estimate,
        }

    def _create_portal_open_ce(self, line_count=1, deadline_hours=24, opening_offset_hours=-1):
        line_vals = [self._tendering_line_vals() for _ in range(line_count)]
        pr = self._submit_and_assign(pr=self._create_draft_pr(line_vals=line_vals))
        envelope = self.env['zvy.closed.envelope'].with_user(self.user_cce).with_company(
            self.company_a
        ).create({
            'request_id': pr.id,
            'invite_partner_ids': [(6, 0, [
                self.partner_a.id, self.partner_b.id, self.partner_c.id,
            ])],
        })
        envelope.with_user(self.user_cce).action_submit_list()
        opening = fields.Datetime.now() + timedelta(hours=opening_offset_hours)
        envelope.with_user(self.user_comm_mgr).write({
            'opening_datetime': opening,
            'bid_deadline': opening + timedelta(hours=deadline_hours)
            if opening_offset_hours < 0
            else fields.Datetime.now() + timedelta(hours=deadline_hours),
        })
        envelope.with_user(self.user_comm_mgr).action_approve_list()
        return pr, envelope

    def _manual_bid(self, envelope, partner, line_prices):
        Bid = self.env['zvy.closed.envelope.bid'].with_user(
            self.user_comm_mgr
        ).with_company(self.company_a)
        bid = Bid.create({
            'envelope_id': envelope.id,
            'partner_id': partner.id,
            'line_ids': [(0, 0, {
                'request_line_id': line.id,
                'price_unit': price,
            }) for line, price in zip(envelope.line_ids, line_prices)],
        })
        return bid

    def test_portal_per_line_prices_sealed_from_other_vendor(self):
        pr, envelope = self._create_portal_open_ce(line_count=2)
        lines = envelope.line_ids
        Bid = self.env['zvy.closed.envelope.bid']
        bid_a = Bid._portal_upsert_bid(
            envelope,
            self.partner_a_contact,
            line_vals=[
                {'request_line_id': lines[0].id, 'price_unit': 10.0},
                {'request_line_id': lines[1].id, 'price_unit': 20.0},
            ],
        )
        Bid._portal_upsert_bid(
            envelope,
            self.partner_b_contact,
            line_vals=[
                {'request_line_id': lines[0].id, 'price_unit': 11.0},
                {'request_line_id': lines[1].id, 'price_unit': 21.0},
            ],
        )
        own = bid_a.with_user(self.user_portal_a).line_ids.sorted('id')
        self.assertEqual(own[0].price_unit, 10.0)
        self.assertEqual(own[1].price_unit, 20.0)

        other_lines = self.env['zvy.closed.envelope.bid.line'].with_user(
            self.user_portal_b
        ).search([('bid_id', '=', bid_a.id)])
        self.assertFalse(other_lines)

        sealed = bid_a.line_ids.with_user(self.user_cce).read(['price_unit'])
        self.assertTrue(all(row['price_unit'] == 0.0 for row in sealed))
        self.assertEqual(pr.procurement_type, 'tendering')

    def test_unique_header_multiple_lines_allowed(self):
        _pr, envelope = self._create_portal_open_ce(line_count=2)
        bid = self._manual_bid(envelope, self.partner_a, [10.0, 15.0])
        self.assertEqual(len(bid.line_ids), 2)
        Bid = self.env['zvy.closed.envelope.bid'].with_user(
            self.user_comm_mgr
        ).with_company(self.company_a)
        with self.assertRaises(ValidationError):
            Bid.create({
                'envelope_id': envelope.id,
                'partner_id': self.partner_a.id,
                'amount': 99.0,
            })

    def test_discount_updates_final_price_and_chatter(self):
        _pr, envelope = self._create_portal_open_ce(line_count=1)
        bid = self._manual_bid(envelope, self.partner_a, [100.0])
        envelope.with_user(self.user_comm_mgr).action_open_bids()
        line = bid.line_ids
        line.with_user(self.user_comm_mgr).write({'discount_percent': 10.0})
        self.assertAlmostEqual(line.final_price, 90.0)
        messages = envelope.message_ids.mapped('body')
        self.assertTrue(any('Discount' in (body or '') and '10' in (body or '') for body in messages))

    def test_partial_award_retender_and_later_ce_po_grouping(self):
        pr, envelope = self._create_portal_open_ce(line_count=3)
        lines = envelope.line_ids.sorted('id')
        bid_a = self._manual_bid(envelope, self.partner_a, [10.0, 20.0, 30.0])
        bid_b = self._manual_bid(envelope, self.partner_b, [11.0, 19.0, 31.0])
        envelope.with_user(self.user_comm_mgr).action_open_bids()

        bid_a.line_ids.filtered(
            lambda l: l.request_line_id == lines[0]
        ).with_user(self.user_comm_mgr).write({'is_winner': True})
        bid_b.line_ids.filtered(
            lambda l: l.request_line_id == lines[1]
        ).with_user(self.user_comm_mgr).write({'is_winner': True})
        envelope.with_user(self.user_comm_mgr).action_select_winner()

        self.assertEqual(envelope.state, 'awarded')
        self.assertEqual(pr.state, 'quote_review')
        self.assertEqual(lines[0].awarded_partner_id, self.partner_a)
        self.assertEqual(lines[1].awarded_partner_id, self.partner_b)
        self.assertTrue(lines[2].ce_retender)
        self.assertFalse(lines[2].awarded_bid_line_id)
        self.assertFalse(pr._has_award_data())

        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        self._approve_all_signatories(pr)
        self.assertEqual(pr.state, 'po_ready')

        action = pr.with_user(self.user_cm).action_create_closed_envelope()
        second = self.env['zvy.closed.envelope'].browse(action['res_id'])
        self.assertNotEqual(second, envelope)
        self.assertEqual(second.line_ids, lines[2])
        second.with_user(self.user_cce).write({
            'invite_partner_ids': [(6, 0, [self.partner_a.id, self.partner_b.id])],
        })
        second.with_user(self.user_cce).action_submit_list()
        opening = fields.Datetime.now() - timedelta(minutes=1)
        second.with_user(self.user_comm_mgr).write({
            'opening_datetime': opening,
            'bid_deadline': opening + timedelta(hours=24),
        })
        second.with_user(self.user_comm_mgr).action_approve_list()
        bid2 = self._manual_bid(second, self.partner_a, [25.0])
        second.with_user(self.user_comm_mgr).action_open_bids()
        bid2.line_ids.with_user(self.user_comm_mgr).write({'is_winner': True})
        second.with_user(self.user_comm_mgr).action_select_winner()
        self.assertFalse(lines[2].ce_retender)
        self.assertEqual(lines[2].awarded_partner_id, self.partner_a)
        self.assertTrue(pr._has_award_data())

        pr.with_user(self.user_cm).action_create_po()
        orders = pr.purchase_order_ids
        self.assertEqual(len(orders), 2)
        by_partner = {order.partner_id: order for order in orders}
        self.assertEqual(len(by_partner[self.partner_a].order_line), 2)
        self.assertEqual(len(by_partner[self.partner_b].order_line), 1)
        self.assertEqual(pr.state, 'done')

    def test_open_blocked_before_datetime_reopen_logged(self):
        _pr, envelope = self._create_portal_open_ce(
            line_count=1,
            opening_offset_hours=2,
            deadline_hours=1,
        )
        with self.assertRaises(UserError):
            envelope.with_user(self.user_comm_mgr).action_open_bids()

        envelope.sudo().write({
            'bid_deadline': fields.Datetime.now() - timedelta(minutes=1),
        })
        new_deadline = fields.Datetime.now() + timedelta(hours=3)
        envelope.with_user(self.user_comm_mgr).with_context(
            zvy_reopen_deadline=new_deadline,
        ).action_reopen_bidding()
        self.assertEqual(envelope.bid_deadline, new_deadline)
        self.assertTrue(any(
            're-opened' in (body or '').lower()
            for body in envelope.message_ids.mapped('body')
        ))

    def test_commission_expert_sets_bid_deadline(self):
        _pr, envelope = self._create_portal_open_ce(line_count=1)
        new_deadline = fields.Datetime.now() + timedelta(hours=10)
        envelope.with_user(self.user_comm_exp).write({
            'bid_deadline': new_deadline,
        })
        self.assertEqual(envelope.bid_deadline, new_deadline)
        with self.assertRaises(UserError):
            envelope.with_user(self.user_comm_exp).write({
                'opening_datetime': fields.Datetime.now(),
            })
