# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyProductProcurementOverride(ZvyTenderingCommon):

    def _overlay(self, product, company, **vals):
        values = {
            'product_tmpl_id': product.product_tmpl_id.id,
            'company_id': company.id,
        }
        values.update(vals)
        return self.env['zvy.product.procurement.company'].create(values)

    def _admin_pr(self, company, product, qty=1.0, estimate=10.0, **extra):
        line_vals = extra.pop('line_vals', [{
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom_id': product.uom_id.id,
            'price_estimate': estimate,
        }])
        vals = {
            'company_id': company.id,
            'requester_id': extra.pop('requester_id', self.env.user.id),
            'description': extra.pop('description', 'Override PR'),
            'line_ids': [(0, 0, line) for line in line_vals],
        }
        vals.update(extra)
        return self.env['zvy.purchase.request'].with_company(company).create(vals)

    def test_type_overlay_applies_per_company(self):
        self._overlay(
            self.product, self.company_a, procurement_type='tendering',
        )
        pr_a = self._create_draft_pr()
        self.assertEqual(pr_a.line_ids.procurement_type, 'tendering')
        self.assertEqual(pr_a.procurement_type, 'tendering')
        self.assertFalse(pr_a.line_ids.is_commission_item)

        pr_b = self._admin_pr(self.company_b, self.product)
        self.assertEqual(pr_b.line_ids.procurement_type, 'enquiry')
        self.assertEqual(pr_b.procurement_type, 'enquiry')
        self.assertFalse(pr_b.is_commission_item)

    def test_overlay_recomputes_existing_draft_line(self):
        pr = self._create_draft_pr()
        self.assertEqual(pr.line_ids.procurement_type, 'enquiry')
        self._overlay(
            self.product, self.company_a, procurement_type='tendering',
        )
        self.assertEqual(pr.line_ids.procurement_type, 'tendering')
        self.assertEqual(pr.procurement_type, 'tendering')

    def test_mixed_submit_uses_resolved_types(self):
        self._overlay(
            self.product, self.company_a, procurement_type='tendering',
        )
        pr = self._create_draft_pr(line_vals=[
            {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 10.0,
            },
            {
                'product_id': self.product_commission.id,
                'product_uom_qty': 1.0,
                'product_uom_id': self.product_commission.uom_id.id,
                'price_estimate': 10.0,
            },
        ])
        self.assertTrue(pr.is_mixed_procurement)
        self.assertFalse(pr.procurement_type)
        with self.assertRaises(ValidationError):
            pr.action_submit()
        new_pr = pr.action_split_mixed()
        self.assertEqual(pr.procurement_type, 'enquiry')
        self.assertEqual(pr.line_ids.product_id, self.product_commission)
        self.assertEqual(new_pr.procurement_type, 'tendering')
        self.assertEqual(new_pr.line_ids.product_id, self.product)
        pr.action_submit()
        new_pr.action_submit()
        self.assertEqual(pr.state, 'submitted')
        self.assertEqual(new_pr.state, 'submitted')

    def test_holding_need_commission_overlay_routes_enquiry(self):
        self.assertFalse(self.product.zvy_need_commission)
        self._overlay(
            self.product,
            self.company_a,
            override_need_commission=True,
            need_commission=True,
        )
        pr = self._create_draft_pr()
        self.assertEqual(pr.line_ids.procurement_type, 'enquiry')
        self.assertTrue(pr.line_ids.is_commission_item)
        self.assertTrue(pr.is_commission_item)
        pr = self._submit_and_assign(pr=pr)
        self.assertFalse(pr.is_high_value)
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        self.assertFalse(pr.commission_case_id)
        self._approve_all_signatories(pr, expected_state='commission')
        self.assertEqual(pr.state, 'commission')
        self.assertTrue(pr.commission_case_id.reason_commission_item)

    def test_holding_overlay_applies_to_child_subsidiary_ignored(self):
        holding = self.env['res.company'].create({'name': 'ZVY Holding Parent'})
        child = self.env['res.company'].create({
            'name': 'ZVY Holding Child',
            'parent_id': holding.id,
        })
        self.assertEqual(child.root_id, holding)
        self.assertEqual(holding, holding._zvy_holding_company())
        self.assertEqual(child._zvy_holding_company(), holding)

        self._overlay(
            self.product,
            holding,
            override_need_commission=True,
            need_commission=True,
        )
        pr_child = self._admin_pr(child, self.product)
        self.assertEqual(pr_child.line_ids.procurement_type, 'enquiry')
        self.assertTrue(pr_child.line_ids.is_commission_item)

        with self.assertRaises(ValidationError):
            self._overlay(
                self.product,
                child,
                override_need_commission=True,
                need_commission=True,
            )

        self._overlay(self.product, child, procurement_type='enquiry')
        pr_child.invalidate_recordset()
        self.assertTrue(pr_child.line_ids.is_commission_item)

    def test_need_commission_ignored_when_resolved_type_is_tendering(self):
        self._overlay(
            self.product_commission,
            self.company_a,
            procurement_type='tendering',
            override_need_commission=True,
            need_commission=True,
        )
        pr = self._create_draft_pr(line_vals=[{
            'product_id': self.product_commission.id,
            'product_uom_qty': 1.0,
            'product_uom_id': self.product_commission.uom_id.id,
            'price_estimate': 10.0,
        }])
        self.assertEqual(pr.line_ids.procurement_type, 'tendering')
        self.assertFalse(pr.line_ids.is_commission_item)
        self.assertFalse(pr.is_commission_item)

    def test_overlay_requires_type_or_commission_flag(self):
        with self.assertRaises(ValidationError):
            self._overlay(self.product, self.company_a)
