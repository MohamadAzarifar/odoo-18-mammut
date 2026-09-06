# -*- coding: utf-8 -*-
import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyCommissionMeeting(ZvyTenderingCommon):

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

    def _make_meeting(self, requesting=None, **vals):
        requesting = requesting or self.company_a
        values = {
            'name': vals.pop('name', 'Commission sitting'),
            'datetime': vals.pop('datetime', fields.Datetime.now()),
            'location': vals.pop('location', 'HQ'),
            'requesting_company_id': requesting.id,
        }
        values.update(vals)
        return self.env['zvy.commission.meeting'].create(values)

    def _attach_minutes(self, meeting, name='minutes.pdf'):
        attachment = self.env['ir.attachment'].create({
            'name': name,
            'datas': base64.b64encode(b'minutes'),
            'res_model': 'zvy.commission.meeting',
            'res_id': meeting.id,
        })
        meeting.minutes_attachment_id = attachment
        return attachment

    def _create_ce_pending(self):
        pr = self._submit_and_assign(pr=self._create_draft_pr(line_vals=[{
            'product_id': self.product_tendering.id,
            'product_uom_qty': 2.0,
            'product_uom_id': self.product_tendering.uom_id.id,
            'price_estimate': 50.0,
        }]))
        envelope = self.env['zvy.closed.envelope'].with_user(
            self.user_cce
        ).with_company(self.company_a).create({
            'request_id': pr.id,
            'invite_partner_ids': [(6, 0, [
                self.partner_a.id, self.partner_b.id, self.partner_c.id,
            ])],
        })
        envelope.with_user(self.user_cce).action_submit_list()
        return pr, envelope

    def test_other_company_case_rejected(self):
        pr_a, case_a = self._route_to_commission()
        pr_b = self.env['zvy.purchase.request'].sudo().with_company(
            self.company_b
        ).create({
            'company_id': self.company_b.id,
            'requester_id': self.user_planner.id,
            'description': 'Other company PR',
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 10.0,
            })],
        })
        case_b = self.env['zvy.commission.case'].sudo().create({
            'request_id': pr_b.id,
        })
        meeting = self._make_meeting()
        self.env['zvy.commission.meeting.case'].create({
            'meeting_id': meeting.id,
            'case_id': case_a.id,
        })
        with self.assertRaises(ValidationError):
            self.env['zvy.commission.meeting.case'].create({
                'meeting_id': meeting.id,
                'case_id': case_b.id,
            })

    def test_held_requires_minutes(self):
        meeting = self._make_meeting()
        with self.assertRaises(UserError):
            meeting.action_mark_held()
        self._attach_minutes(meeting)
        meeting.action_mark_held()
        self.assertEqual(meeting.state, 'held')

    def test_external_attendee_without_user(self):
        meeting = self._make_meeting()
        guest = self.env['zvy.commission.meeting.attendee'].create({
            'meeting_id': meeting.id,
            'kind': 'external',
            'name': 'Guest Advisor',
            'role': 'Legal',
        })
        self.assertFalse(guest.user_id)
        self.assertEqual(guest.name, 'Guest Advisor')
        with self.assertRaises(ValidationError):
            self.env['zvy.commission.meeting.attendee'].create({
                'meeting_id': meeting.id,
                'kind': 'external',
                'name': 'No Role',
            })
        internal = self.env['zvy.commission.meeting.attendee'].create({
            'meeting_id': meeting.id,
            'kind': 'internal',
            'user_id': self.user_comm_mgr.id,
        })
        self.assertEqual(internal.name, self.user_comm_mgr.name)

    def test_per_pr_decision_and_transfer_keeps_history(self):
        _pr1, case1 = self._route_to_commission()
        _pr2, case2 = self._route_to_commission()
        meeting = self._make_meeting()
        row1 = self.env['zvy.commission.meeting.case'].create({
            'meeting_id': meeting.id,
            'case_id': case1.id,
        })
        row2 = self.env['zvy.commission.meeting.case'].create({
            'meeting_id': meeting.id,
            'case_id': case2.id,
        })
        self.assertEqual(case1.state, 'meeting')
        self.assertEqual(case2.state, 'meeting')
        self._attach_minutes(meeting)
        meeting.action_mark_held()
        row1.write({'decision': 'approved'})
        self.assertEqual(row1.review_status, 'reviewed')
        self.assertEqual(case1.state, 'approved')
        self.assertEqual(row2.decision, 'undecided')

        meeting2 = self._make_meeting(name='Later sitting')
        wizard = self.env['zvy.meeting.transfer.wizard'].create({
            'meeting_case_id': row2.id,
            'target_meeting_id': meeting2.id,
        })
        wizard.action_confirm()
        self.assertEqual(row2.review_status, 'removed')
        self.assertEqual(len(meeting.meeting_case_ids), 2)
        self.assertIn(row1, meeting.meeting_case_ids)
        self.assertIn(row2, meeting.meeting_case_ids)
        moved = meeting2.meeting_case_ids.filtered(lambda r: r.case_id == case2)
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved.review_status, 'pending')
        self.assertEqual(case2.meeting_id, meeting2)
        self.assertEqual(case1.meeting_id, meeting)

    def test_cancelled_meeting_keeps_history(self):
        _pr, case = self._route_to_commission()
        meeting = self._make_meeting()
        row = self.env['zvy.commission.meeting.case'].create({
            'meeting_id': meeting.id,
            'case_id': case.id,
        })
        meeting.action_cancel()
        self.assertEqual(meeting.state, 'cancelled')
        self.assertTrue(row.exists())
        self.assertEqual(row.review_status, 'pending')
        self.assertFalse(case.meeting_id)

    def test_meeting_company_is_holding(self):
        meeting = self._make_meeting()
        self.assertEqual(meeting.company_id, self.company_a.root_id)
        self.assertEqual(meeting.company_id, self.company_a)

        holding = self.env['res.company'].create({'name': 'ZVY Holding Co'})
        sub = self.env['res.company'].create({
            'name': 'ZVY Sub Co',
            'parent_id': holding.id,
        })
        self.assertEqual(sub.root_id, holding)
        nested = self._make_meeting(requesting=sub, name='Holding sitting')
        self.assertEqual(nested.company_id, holding)
        self.assertEqual(nested.requesting_company_id, sub)

    def test_open_bids_blocked_until_meeting_held(self):
        pr, envelope = self._create_ce_pending()
        opening = fields.Datetime.now() - timedelta(hours=2)
        envelope.with_user(self.user_comm_mgr).write({
            'opening_datetime': opening,
            'bid_deadline': opening + timedelta(hours=24),
        })
        envelope.with_user(self.user_comm_mgr).action_approve_list()
        self.assertEqual(envelope.state, 'portal_open')

        case = self.env['zvy.commission.case'].create({
            'request_id': pr.id,
        })
        sitting = fields.Datetime.now() - timedelta(hours=1)
        meeting = self._make_meeting(datetime=sitting)
        self.env['zvy.commission.meeting.case'].create({
            'meeting_id': meeting.id,
            'case_id': case.id,
        })
        self.assertEqual(envelope.opening_datetime, sitting)
        with self.assertRaises(UserError):
            envelope.with_user(self.user_comm_mgr).action_open_bids()
        self._attach_minutes(meeting)
        meeting.action_mark_held()
        envelope.with_user(self.user_comm_mgr).action_open_bids()
        self.assertEqual(envelope.state, 'opened')
