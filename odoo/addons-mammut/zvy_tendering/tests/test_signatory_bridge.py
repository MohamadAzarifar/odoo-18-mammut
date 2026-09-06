# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvySignatoryBridge(ZvyTenderingCommon):

    def _route_to_signatory(self, sole_source=False):
        if sole_source:
            self._ensure_sole_source_avl()
        line_vals = [{
            'product_id': self.product.id,
            'product_uom_qty': 2.0,
            'product_uom_id': self.product.uom_id.id,
            'price_estimate': 50.0,
        }]
        pr = self._create_draft_pr(line_vals=line_vals)
        self.assertEqual(pr.has_sole_source, sole_source)
        pr = self._submit_and_assign(pr=pr)
        self._add_quotes(pr, count=1 if sole_source else 3)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        self.assertTrue(pr.sudo().approval_request_id)
        return pr

    def test_approve_moves_to_po_ready(self):
        pr = self._route_to_signatory()
        self._approve_all_signatories(pr)
        self.assertEqual(pr.state, 'po_ready')

    def test_refuse_returns_to_cm_review(self):
        pr = self._route_to_signatory()
        approval = pr.sudo().approval_request_id
        pending = approval.approver_ids.filtered(lambda a: a.status == 'pending')
        pending[0].with_user(pending[0].user_id).action_refuse()
        self.assertEqual(approval.request_status, 'refused')
        self.assertEqual(pr.state, 'cm_review')

    def test_resubmit_signatory_after_refuse(self):
        pr = self._route_to_signatory()
        approval = pr.sudo().approval_request_id
        pending = approval.approver_ids.filtered(lambda a: a.status == 'pending')
        pending[0].with_user(pending[0].user_id).action_refuse()
        self.assertEqual(pr.state, 'cm_review')

        pr.with_user(self.user_cm).action_resubmit_signatory()
        self.assertEqual(pr.state, 'signatory')
        self.assertTrue(pr.sudo().approval_request_id)
        self.assertNotEqual(pr.sudo().approval_request_id, approval)
        self.assertEqual(pr.sudo().approval_request_id.request_status, 'pending')

    def test_sole_source_includes_ceo(self):
        pr = self._route_to_signatory(sole_source=True)
        approval = pr.sudo().approval_request_id
        approver_users = approval.approver_ids.mapped('user_id')
        self.assertIn(self.user_signatory, approver_users)
        self.assertIn(self.user_ceo, approver_users)
        ceo_approver = approval.approver_ids.filtered(
            lambda a: a.user_id == self.user_ceo
        )
        self.assertTrue(ceo_approver.required)
        # CEO must be last in sequence.
        self.assertEqual(
            ceo_approver.sequence,
            max(approval.approver_ids.mapped('sequence')),
        )

        # Signatory first, then CEO.
        self._approve_all_signatories(pr)
        self.assertEqual(pr.state, 'po_ready')

    def test_cannot_create_po_from_non_po_ready(self):
        pr = self._route_to_signatory()
        with self.assertRaises(UserError):
            pr.with_user(self.user_cm).action_create_po()

    def test_non_cm_cannot_create_po(self):
        pr = self._route_to_signatory()
        self._approve_all_signatories(pr)
        with self.assertRaises(UserError):
            pr.with_user(self.user_cce).action_create_po()

    def test_create_po_from_awarded_quotes(self):
        pr = self._route_to_signatory()
        self._approve_all_signatories(pr)
        action = pr.with_user(self.user_cm).action_create_po()
        self.assertEqual(pr.state, 'done')
        self.assertEqual(len(pr.sudo().purchase_order_ids), 1)
        po = pr.sudo().purchase_order_ids
        self.assertEqual(po.partner_id, self.partner_a)
        self.assertEqual(po.zvy_purchase_request_id, pr)
        self.assertEqual(po.origin, pr.name)
        self.assertEqual(len(po.order_line), 1)
        self.assertEqual(po.order_line.price_unit, pr.line_ids.awarded_quote_id.price_unit)
        self.assertEqual(action['res_model'], 'purchase.order')

    def test_cannot_force_po_ready_while_approval_pending(self):
        pr = self._route_to_signatory()
        self.assertEqual(pr.sudo().approval_request_id.request_status, 'pending')
        with self.assertRaises(UserError):
            pr.sudo().write({'state': 'po_ready'})

    def test_commission_path_to_po(self):
        self._force_large_bands()
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        approval = self._approve_all_signatories(pr, expected_state='commission')
        self.assertEqual(pr.state, 'commission')
        self._approve_commission_without_meeting(pr.commission_case_id)
        self.assertEqual(pr.state, 'po_ready')
        self.assertEqual(pr.sudo().approval_request_id, approval)
        pr.with_user(self.user_cm).action_create_po()
        self.assertEqual(pr.state, 'done')
        self.assertTrue(pr.sudo().purchase_order_ids)

    def test_signatory_can_read_linked_pr_context(self):
        pr = self._route_to_signatory()
        pr_as_sig = pr.with_user(self.user_signatory)
        self.assertEqual(pr_as_sig.name, pr.name)
        self.assertTrue(pr_as_sig.line_ids)
        self.assertTrue(pr_as_sig.quote_ids)
        self.assertTrue(pr_as_sig.line_ids.awarded_quote_id)
        # Form loads sole_source / allowed_partner_ids which touch AVL.
        self.assertTrue(isinstance(pr_as_sig.line_ids.sole_source, bool))
        self.assertTrue(pr_as_sig.quote_ids.allowed_partner_ids)

    def test_signatory_cannot_write_pr(self):
        pr = self._route_to_signatory()
        with self.assertRaises(AccessError):
            pr.with_user(self.user_signatory).check_access('write')
        with self.assertRaises(AccessError):
            self.env['zvy.purchase.request'].with_user(
                self.user_signatory
            ).check_access('write')

    def test_non_approver_signatory_cannot_read_pr(self):
        pr = self._route_to_signatory()
        with self.assertRaises(AccessError):
            pr.with_user(self.user_signatory_other).read(['name'])

    def test_signatory_opens_pr_from_approval(self):
        pr = self._route_to_signatory()
        approval = pr.sudo().approval_request_id
        action = approval.with_user(self.user_signatory).action_open_zvy_purchase_request()
        self.assertEqual(action['res_model'], 'zvy.purchase.request')
        self.assertEqual(action['res_id'], pr.id)
        opened = self.env['zvy.purchase.request'].with_user(
            self.user_signatory
        ).browse(action['res_id'])
        self.assertEqual(opened.name, pr.name)
