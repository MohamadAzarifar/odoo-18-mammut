# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyReturnLastApprover(ZvyTenderingCommon):

    def _enable_two_signatories(self):
        self.employee_signatory_other.job_id = self.job_signatory

    def _route_to_signatory(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        return pr

    def _approvers_in_order(self, approval):
        return approval.approver_ids.sorted(lambda a: (a.sequence, a.id))

    def test_second_signatory_returns_to_first(self):
        self._enable_two_signatories()
        pr = self._route_to_signatory()
        approval = pr.sudo().approval_request_id
        first, second = self._approvers_in_order(approval)
        first.with_user(first.user_id).action_approve()
        approval.invalidate_recordset()
        self.assertEqual(second.status, 'pending')

        with self.assertRaises(ValidationError):
            self._refuse_signatory(second, reason='   ')

        action = second.with_user(second.user_id).action_refuse()
        self.assertEqual(
            action['res_model'], 'zvy.request.signatory.return.wizard',
        )
        wizard = self.env['zvy.request.signatory.return.wizard'].with_user(
            second.user_id
        ).create({
            'approval_request_id': approval.id,
            'reason': 'Please revisit the award',
        })
        wizard.action_confirm()

        approval.invalidate_recordset()
        first.invalidate_recordset()
        second.invalidate_recordset()
        self.assertEqual(pr.state, 'signatory')
        self.assertEqual(approval.request_status, 'pending')
        self.assertEqual(first.status, 'pending')
        self.assertEqual(second.status, 'waiting')
        self.assertEqual(pr.return_reason, 'Please revisit the award')
        self.assertTrue(pr.message_ids.filtered(
            lambda m: m.body and 'Please revisit the award' in (m.body or '')
        ))

    def test_first_signatory_returns_to_cm_then_planner(self):
        pr = self._route_to_signatory()
        old = pr.sudo().approval_request_id
        pending = old.approver_ids.filtered(lambda a: a.status == 'pending')
        self._refuse_signatory(pending[0], reason='Missing dossier note')
        self.assertEqual(old.request_status, 'refused')
        self.assertEqual(pr.state, 'cm_review')
        self.assertEqual(pr.return_reason, 'Missing dossier note')

        pr.with_user(self.user_cm)._action_return_correction('Fix the header')
        self.assertEqual(pr.state, 'correction')
        pr.with_user(self.user_planner).write({'description': 'Corrected'})
        pr.with_user(self.user_planner).action_submit()
        self.assertEqual(pr.state, 'submitted')

        pr.with_user(self.user_cm)._action_assign_experts({
            line.id: [self.user_cce.id] for line in pr.line_ids
        })
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        new = pr.sudo().approval_request_id
        self.assertNotEqual(new, old)
        self.assertEqual(new.request_status, 'pending')

    def test_cm_return_to_expert_keeps_assignment(self):
        pr = self._route_to_signatory()
        pending = pr.sudo().approval_request_id.approver_ids.filtered(
            lambda a: a.status == 'pending'
        )
        self._refuse_signatory(pending[0], reason='Need new quotes')
        self.assertEqual(pr.state, 'cm_review')

        quote = pr.sudo().quote_ids.filtered(
            lambda q: q.state in ('submitted', 'accepted')
        )[:1]
        self.assertTrue(quote)

        wizard = self.env['zvy.request.return.wizard'].with_user(
            self.user_cm
        ).create({
            'request_id': pr.id,
            'reason': 'Re-price the enquiry',
            'destination': 'expert',
        })
        wizard.action_confirm()
        self.assertEqual(pr.state, 'inquiry')
        self.assertEqual(pr.line_ids.expert_user_ids, self.user_cce)
        quote.invalidate_recordset()
        self.assertEqual(quote.state, 'draft')
        self.assertFalse(pr.line_ids.awarded_quote_id)
        quote.with_user(self.user_cce).write({'price_unit': 42.0})
        self.assertEqual(quote.price_unit, 42.0)

    def test_cm_return_to_expert_reassign(self):
        pr = self._route_to_signatory()
        pending = pr.sudo().approval_request_id.approver_ids.filtered(
            lambda a: a.status == 'pending'
        )
        self._refuse_signatory(pending[0], reason='Wrong expert')
        wizard = self.env['zvy.request.return.wizard'].with_user(
            self.user_cm
        ).with_context(default_request_id=pr.id).create({
            'request_id': pr.id,
            'reason': 'Give to the other expert',
            'destination': 'expert',
            'reassign_experts': True,
        })
        wizard.line_ids.write({'expert_user_ids': [(6, 0, [self.user_cce_other.id])]})
        wizard.action_confirm()
        self.assertEqual(pr.state, 'inquiry')
        self.assertEqual(pr.line_ids.expert_user_ids, self.user_cce_other)

    def test_submitted_return_stays_planner_only(self):
        pr = self._create_draft_pr()
        pr.action_submit()
        wizard = self.env['zvy.request.return.wizard'].with_user(
            self.user_cm
        ).create({
            'request_id': pr.id,
            'reason': 'Missing quantity',
            'destination': 'expert',
        })
        wizard.action_confirm()
        self.assertEqual(pr.state, 'correction')

    def test_cm_reject_remains_terminal(self):
        pr = self._route_to_signatory()
        pending = pr.sudo().approval_request_id.approver_ids.filtered(
            lambda a: a.status == 'pending'
        )
        self._refuse_signatory(pending[0], reason='Stop')
        pr.with_user(self.user_cm)._action_reject('Cancelled by CM')
        self.assertEqual(pr.state, 'rejected')

    def test_commission_enquiry_corrections_to_last_signatory(self):
        self._enable_two_signatories()
        self._force_large_bands()
        pr = self._route_to_signatory()
        old = self._approve_all_signatories(pr, expected_state='commission')
        self.assertEqual(old.request_status, 'approved')
        case = pr.commission_case_id.with_user(self.user_comm_mgr)
        case._action_assign_experts([self.user_comm_exp.id])

        action = case.action_manager_corrections()
        self.assertEqual(
            action['res_model'], 'zvy.commission.corrections.wizard',
        )
        with self.assertRaises(ValidationError):
            case._action_manager_corrections('   ')
        case._action_manager_corrections('Dossier incomplete')

        self.assertEqual(case.state, 'corrections')
        self.assertEqual(pr.state, 'signatory')
        new = pr.sudo().approval_request_id
        self.assertNotEqual(new, old)
        self.assertTrue(new.zvy_resume_commission)
        ordered = self._approvers_in_order(new)
        self.assertEqual(ordered[-1].status, 'pending')
        self.assertTrue(all(a.status == 'approved' for a in ordered[:-1]))

        ordered[-1].with_user(ordered[-1].user_id).action_approve()
        self.assertEqual(pr.state, 'commission')
        self.assertEqual(case.state, 'open')

    def test_commission_tendering_corrections_to_cm(self):
        self._force_large_bands()
        pr, envelope = self._tendering_to_commission()
        self.assertFalse(pr.sudo().approval_request_id)
        case = pr.commission_case_id.with_user(self.user_comm_mgr)
        case._action_assign_experts([self.user_comm_exp.id])
        case._action_manager_corrections('Re-tender the list')
        self.assertEqual(case.state, 'corrections')
        self.assertEqual(pr.state, 'cm_review')

        wizard = self.env['zvy.request.return.wizard'].with_user(
            self.user_cm
        ).create({
            'request_id': pr.id,
            'reason': 'Experts must rebuild the list',
            'destination': 'expert',
        })
        wizard.action_confirm()
        self.assertEqual(pr.state, 'inquiry')
        envelope.invalidate_recordset()
        self.assertEqual(envelope.state, 'draft')
        envelope.with_user(self.user_cce).write({
            'invite_partner_ids': [(6, 0, [self.partner_a.id, self.partner_b.id])],
        })

    def test_resubmit_signatory_after_first_refuse_is_new_chain(self):
        pr = self._route_to_signatory()
        old = pr.sudo().approval_request_id
        pending = old.approver_ids.filtered(lambda a: a.status == 'pending')
        self._refuse_signatory(pending[0], reason='Send again')
        pr.with_user(self.user_cm).action_resubmit_signatory()
        self.assertEqual(pr.state, 'signatory')
        new = pr.sudo().approval_request_id
        self.assertNotEqual(new, old)
        self.assertEqual(new.request_status, 'pending')
        self.assertFalse(new.zvy_resume_commission)

    def _tendering_to_commission(self):
        pr, envelope = self._create_tendering_pending()
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
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'commission')
        return pr, envelope

    def _create_tendering_pending(self):
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
