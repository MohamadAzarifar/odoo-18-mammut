# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyProductTypeAndSplit(ZvyTenderingCommon):

    def _tendering_line(self, qty=1.0, estimate=10.0):
        return {
            'product_id': self.product_tendering.id,
            'product_uom_qty': qty,
            'product_uom_id': self.product_tendering.uom_id.id,
            'price_estimate': estimate,
        }

    def _enquiry_line(self, product=None, qty=1.0, estimate=10.0):
        product = product or self.product
        return {
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom_id': product.uom_id.id,
            'price_estimate': estimate,
        }

    def test_product_defaults_enquiry_without_commission(self):
        self.assertEqual(self.product.zvy_procurement_type, 'enquiry')
        self.assertFalse(self.product.zvy_need_commission)
        self.assertEqual(self.product_commission.zvy_procurement_type, 'enquiry')
        self.assertTrue(self.product_commission.zvy_need_commission)
        self.assertEqual(self.product_tendering.zvy_procurement_type, 'tendering')
        self.assertFalse(self.product_tendering.zvy_need_commission)

    def test_tendering_clears_need_commission(self):
        product = self.env['product.product'].create({
            'name': 'ZVY Switch To Tendering',
            'type': 'consu',
            'zvy_need_commission': True,
        })
        self.assertTrue(product.zvy_need_commission)
        product.product_tmpl_id.write({'zvy_procurement_type': 'tendering'})
        self.assertEqual(product.zvy_procurement_type, 'tendering')
        self.assertFalse(product.zvy_need_commission)

        created = self.env['product.product'].create({
            'name': 'ZVY Tendering With Flag',
            'type': 'consu',
            'zvy_procurement_type': 'tendering',
            'zvy_need_commission': True,
        })
        self.assertFalse(created.zvy_need_commission)

    def test_mixed_submit_rpc_raises(self):
        pr = self._create_draft_pr(line_vals=[
            self._enquiry_line(),
            self._tendering_line(),
        ])
        self.assertTrue(pr.is_mixed_procurement)
        self.assertFalse(pr.procurement_type)
        with self.assertRaises(ValidationError):
            pr.action_submit()
        self.assertEqual(pr.state, 'draft')

    def test_mixed_submit_ui_opens_split_wizard(self):
        pr = self._create_draft_pr(line_vals=[
            self._enquiry_line(),
            self._tendering_line(),
        ])
        action = pr.with_context(zvy_ui_submit=True).action_submit()
        self.assertEqual(action['res_model'], 'zvy.request.split.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(pr.state, 'draft')

    def test_split_moves_tendering_lines_and_leaves_both_unsubmitted(self):
        pr = self._create_draft_pr(line_vals=[
            self._enquiry_line(qty=2.0, estimate=20.0),
            self._tendering_line(qty=3.0, estimate=30.0),
        ])
        original_name = pr.name
        new_pr = pr.action_split_mixed()
        self.assertEqual(pr.state, 'draft')
        self.assertEqual(new_pr.state, 'draft')
        self.assertNotEqual(new_pr.name, original_name)
        self.assertTrue(new_pr.name.startswith('PR/'))
        self.assertEqual(pr.procurement_type, 'enquiry')
        self.assertEqual(new_pr.procurement_type, 'tendering')
        self.assertFalse(pr.is_mixed_procurement)
        self.assertEqual(pr.split_request_id, new_pr)
        self.assertEqual(new_pr.split_from_id, pr)
        self.assertEqual(pr.requester_id, self.user_planner)
        self.assertEqual(new_pr.requester_id, self.user_planner)
        self.assertEqual(pr.line_ids.product_id, self.product)
        self.assertEqual(new_pr.line_ids.product_id, self.product_tendering)
        pr.action_submit()
        new_pr.action_submit()
        self.assertEqual(pr.state, 'submitted')
        self.assertEqual(new_pr.state, 'submitted')

    def test_split_from_correction_keeps_original_state(self):
        pr = self._create_draft_pr(line_vals=[self._enquiry_line()])
        pr.action_submit()
        pr.with_user(self.user_cm)._action_return_correction('Need another item')
        pr.with_user(self.user_planner).write({
            'line_ids': [(0, 0, self._tendering_line())],
        })
        self.assertTrue(pr.is_mixed_procurement)
        new_pr = pr.with_user(self.user_planner).action_split_mixed()
        self.assertEqual(pr.state, 'correction')
        self.assertEqual(new_pr.state, 'draft')

    def test_wizard_confirm_splits(self):
        pr = self._create_draft_pr(line_vals=[
            self._enquiry_line(),
            self._tendering_line(),
        ])
        wizard = self.env['zvy.request.split.wizard'].with_user(
            self.user_planner
        ).create({'request_id': pr.id})
        action = wizard.action_confirm()
        self.assertEqual(pr.procurement_type, 'enquiry')
        self.assertTrue(pr.split_request_id)
        self.assertEqual(action['res_id'], pr.id)

    def test_enquiry_cannot_create_closed_envelope(self):
        pr = self._submit_and_assign()
        self.assertEqual(pr.procurement_type, 'enquiry')
        with self.assertRaises(UserError):
            pr.with_user(self.user_cce).action_create_closed_envelope()
        with self.assertRaises(UserError):
            self.env['zvy.closed.envelope'].with_user(self.user_cce).with_company(
                self.company_a
            ).create({'request_id': pr.id})

    def test_tendering_cannot_record_or_submit_quotes(self):
        pr = self._submit_and_assign(pr=self._create_draft_pr(line_vals=[
            self._tendering_line(),
        ]))
        self.assertEqual(pr.procurement_type, 'tendering')
        with self.assertRaises(UserError):
            self.env['zvy.quote'].with_user(self.user_cce).with_company(
                self.company_a
            ).create({
                'line_id': pr.line_ids.id,
                'partner_id': self.partner_a.id,
                'price_unit': 12.0,
            })
        with self.assertRaises(UserError):
            pr.with_user(self.user_cce).action_submit_quotes()
        envelope = pr.with_user(self.user_cce).action_create_closed_envelope()
        self.assertEqual(envelope['res_model'], 'zvy.closed.envelope')
