# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyPartialPo(ZvyTenderingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_b = cls.env['product.product'].create({
            'name': 'ZVY Test Product B',
            'type': 'consu',
            'list_price': 80.0,
        })

    def _enquiry_line(self, product, qty=2.0, estimate=50.0):
        return {
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom_id': product.uom_id.id,
            'price_estimate': estimate,
        }

    def _route_two_lines_to_po_ready(self, award_partners=None):
        pr = self._create_draft_pr(line_vals=[
            self._enquiry_line(self.product),
            self._enquiry_line(self.product_b),
        ])
        pr = self._submit_and_assign(pr=pr)
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        if award_partners is None:
            self._award_quotes(pr)
        else:
            for line, partner in zip(pr.sudo().line_ids, award_partners):
                quote = line.quote_ids.filtered(
                    lambda q, p=partner: q.state == 'submitted' and q.partner_id == p
                )[:1]
                self.assertTrue(quote, 'Expected a submitted quote for %s' % partner.name)
                line.with_user(self.user_cm).write({
                    'awarded_quote_id': quote.id,
                    'award_not_lowest_reason': (
                        False if quote.partner_id == self.partner_a
                        else 'Split vendors for grouping test'
                    ),
                })
        pr.with_user(self.user_cm).action_approve_quotes()
        self._approve_all_signatories(pr)
        self.assertEqual(pr.state, 'po_ready')
        return pr

    def _create_po_wizard(self, pr, user=None):
        user = user or self.user_cm
        Wizard = self.env['zvy.request.create.po.wizard'].with_user(user)
        vals = Wizard.with_context(default_request_id=pr.id).default_get(
            ['request_id', 'line_ids']
        )
        return Wizard.create(vals)

    def test_partial_create_po_keeps_pr_po_ready(self):
        pr = self._route_two_lines_to_po_ready()
        lines = pr.sudo().line_ids.sorted('id')
        self.assertEqual(set(lines.mapped('purchase_state')), {'pending'})

        wizard = self._create_po_wizard(pr)
        wizard.line_ids.filtered(lambda l: l.line_id == lines[1]).selected = False
        wizard.action_confirm()

        self.assertEqual(pr.state, 'po_ready')
        self.assertEqual(lines[0].purchase_state, 'ordered')
        self.assertEqual(lines[1].purchase_state, 'pending')
        orders = pr.sudo().purchase_order_ids
        self.assertEqual(len(orders), 1)
        self.assertEqual(len(orders.order_line), 1)
        self.assertEqual(
            orders.order_line.zvy_purchase_request_line_id, lines[0],
        )

    def test_second_po_marks_request_done(self):
        pr = self._route_two_lines_to_po_ready()
        lines = pr.sudo().line_ids.sorted('id')
        wizard = self._create_po_wizard(pr)
        wizard.line_ids.filtered(lambda l: l.line_id == lines[1]).selected = False
        wizard.action_confirm()
        self.assertEqual(pr.state, 'po_ready')

        pr.with_user(self.user_cm).action_create_po()
        self.assertEqual(pr.state, 'done')
        self.assertEqual(set(lines.mapped('purchase_state')), {'ordered'})
        self.assertEqual(len(pr.sudo().purchase_order_ids), 2)

    def test_reject_po_ready_cancels_pending_lines(self):
        pr = self._route_two_lines_to_po_ready()
        lines = pr.sudo().line_ids.sorted('id')
        wizard = self._create_po_wizard(pr)
        wizard.line_ids.filtered(lambda l: l.line_id == lines[1]).selected = False
        wizard.action_confirm()
        po = pr.sudo().purchase_order_ids
        self.assertEqual(len(po), 1)

        pr.with_user(self.user_cm)._action_reject('Remaining items not needed')
        self.assertEqual(pr.state, 'rejected')
        self.assertEqual(lines[0].purchase_state, 'ordered')
        self.assertEqual(lines[1].purchase_state, 'cancelled')
        self.assertEqual(pr.sudo().purchase_order_ids, po)
        with self.assertRaises(UserError):
            pr.with_user(self.user_cm).action_create_po()

    def test_non_cm_cannot_create_po_except_commission_manager(self):
        pr = self._route_two_lines_to_po_ready()
        with self.assertRaises(UserError):
            pr.with_user(self.user_cce).action_create_po()
        pr.with_user(self.user_comm_mgr).action_create_po()
        self.assertEqual(pr.state, 'done')
        orders = pr.sudo().purchase_order_ids
        self.assertEqual(len(orders), 1)
        self.assertEqual(len(orders.order_line), 2)

    def test_full_selection_groups_by_vendor(self):
        pr = self._route_two_lines_to_po_ready(
            award_partners=[self.partner_a, self.partner_b],
        )
        action = pr.with_user(self.user_cm).action_create_po()
        self.assertEqual(pr.state, 'done')
        orders = pr.sudo().purchase_order_ids
        self.assertEqual(len(orders), 2)
        self.assertEqual(
            set(orders.mapped('partner_id')),
            {self.partner_a, self.partner_b},
        )
        self.assertEqual(action['res_model'], 'purchase.order')
        self.assertEqual(set(pr.sudo().line_ids.mapped('purchase_state')), {'ordered'})

    def test_ui_create_po_opens_wizard_with_all_selected(self):
        pr = self._route_two_lines_to_po_ready()
        action = pr.with_user(self.user_cm).with_context(
            zvy_ui_create_po=True,
        ).action_create_po()
        self.assertEqual(action['res_model'], 'zvy.request.create.po.wizard')
        wizard = self._create_po_wizard(pr)
        self.assertEqual(len(wizard.line_ids), 2)
        self.assertTrue(all(wizard.line_ids.mapped('selected')))
        self.assertEqual(pr.state, 'po_ready')

    def test_wizard_empty_selection_raises(self):
        pr = self._route_two_lines_to_po_ready()
        wizard = self._create_po_wizard(pr)
        wizard.line_ids.write({'selected': False})
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertEqual(pr.state, 'po_ready')
        self.assertFalse(pr.sudo().purchase_order_ids)
