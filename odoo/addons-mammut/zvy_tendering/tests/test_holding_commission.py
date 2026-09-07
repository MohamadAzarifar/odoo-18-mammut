# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyHoldingCommission(ZvyTenderingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.holding = cls.env['res.company'].create({'name': 'ZVY Head Holding'})
        cls.child_a = cls.env['res.company'].create({
            'name': 'ZVY Sub A',
            'parent_id': cls.holding.id,
        })
        cls.child_b = cls.env['res.company'].create({
            'name': 'ZVY Sub B',
            'parent_id': cls.holding.id,
        })
        cls.Avl.create({
            'partner_id': cls.partner_a.id,
            'company_id': cls.child_a.id,
        })
        cls.Avl.create({
            'partner_id': cls.partner_a.id,
            'company_id': cls.child_b.id,
        })
        cls.user_holding_comm_mgr = cls._make_company_user(
            'ZVY Holding Comm Mgr',
            'zvy_holding_comm_mgr',
            cls.holding,
            cls.group_comm_mgr,
        )
        cls.user_holding_cm = cls._make_company_user(
            'ZVY Holding Commercial Mgr',
            'zvy_holding_cm',
            cls.holding,
            cls.group_cm,
        )
        cls.user_child_a_cm = cls._make_company_user(
            'ZVY Child A CM',
            'zvy_child_a_cm',
            cls.child_a,
            cls.group_cm,
        )
        cls.user_child_a_cce = cls._make_company_user(
            'ZVY Child A CCE',
            'zvy_child_a_cce',
            cls.child_a,
            cls.group_cce,
        )

    @classmethod
    def _make_company_user(cls, name, login, company, group):
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': name,
            'login': login,
            'email': '%s@example.com' % login,
            'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                group.id,
            ])],
        })

    def _as_user(self, user, model):
        return self.env[model].with_user(user).with_context(
            allowed_company_ids=[user.company_id.id],
        )

    def _pr_on(self, company, product=None):
        product = product or self.product
        return self.env['zvy.purchase.request'].with_company(company).create({
            'company_id': company.id,
            'requester_id': self.env.user.id,
            'description': 'Holding FR-46 PR %s' % company.name,
            'line_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'product_uom_id': product.uom_id.id,
                'price_estimate': 50.0,
            })],
        })

    def _case_on(self, company):
        pr = self._pr_on(company)
        return self.env['zvy.commission.case'].create({
            'request_id': pr.id,
            'reason_high_value': True,
        }), pr

    def _ce_pending_on(self, company):
        pr = self._pr_on(company, product=self.product_tendering)
        pr.action_submit()
        pr._action_assign_experts({
            line.id: [self.user_cce.id] for line in pr.line_ids
        })
        envelope = self.env['zvy.closed.envelope'].with_company(company).create({
            'request_id': pr.id,
        })
        opening = fields.Datetime.now() + timedelta(hours=1)
        envelope.write({
            'state': 'list_pending',
            'opening_datetime': opening,
            'bid_deadline': opening + timedelta(hours=24),
        })
        return pr, envelope

    def test_standalone_company_is_its_own_holding(self):
        self.assertEqual(self.company_a._zvy_holding_company(), self.company_a)
        pr = self._create_draft_pr()
        self.assertEqual(pr.holding_company_id, self.company_a)
        case = self.env['zvy.commission.case'].create({
            'request_id': pr.id,
        })
        self.assertEqual(case.company_id, self.company_a)
        self.assertEqual(case.holding_company_id, self.company_a)

    def test_nested_root_id_skips_mid_parent(self):
        mid = self.env['res.company'].create({
            'name': 'ZVY Mid',
            'parent_id': self.holding.id,
        })
        leaf = self.env['res.company'].create({
            'name': 'ZVY Leaf',
            'parent_id': mid.id,
        })
        self.assertEqual(leaf.parent_id, mid)
        self.assertEqual(leaf.root_id, self.holding)
        self.assertEqual(leaf._zvy_holding_company(), self.holding)
        pr = self._pr_on(leaf)
        self.assertEqual(pr.holding_company_id, self.holding)
        case, _pr = self._case_on(leaf)
        self.assertEqual(case.company_id, leaf)
        self.assertEqual(case.holding_company_id, self.holding)
        self.assertNotEqual(case.holding_company_id, mid)

    def test_holding_only_commission_manager_reads_and_acts_on_descendants(self):
        case_a, pr_a = self._case_on(self.child_a)
        case_b, pr_b = self._case_on(self.child_b)
        self.assertEqual(case_a.holding_company_id, self.holding)
        self.assertEqual(case_b.holding_company_id, self.holding)

        Case = self._as_user(self.user_holding_comm_mgr, 'zvy.commission.case')
        found = Case.search([('id', 'in', [case_a.id, case_b.id])])
        self.assertEqual(found, case_a | case_b)
        Case.browse(case_a.id).check_access('read')
        Case.browse(case_a.id).check_access('write')
        Case.browse(case_a.id).write({'manager_notes': 'Holding review'})
        Request = self._as_user(self.user_holding_comm_mgr, 'zvy.purchase.request')
        Request.browse(pr_a.id).check_access('read')
        Request.browse(pr_b.id).check_access('read')

        _pr, envelope_a = self._ce_pending_on(self.child_a)
        _pr, envelope_b = self._ce_pending_on(self.child_b)
        Envelope = self._as_user(self.user_holding_comm_mgr, 'zvy.closed.envelope')
        self.assertEqual(
            Envelope.search([('id', 'in', [envelope_a.id, envelope_b.id])]),
            envelope_a | envelope_b,
        )
        Envelope.browse(envelope_a.id).action_approve_list()
        self.assertEqual(envelope_a.state, 'portal_open')
        Envelope.browse(envelope_b.id).action_approve_list()
        self.assertEqual(envelope_b.state, 'portal_open')

    def test_company_a_user_cannot_read_company_b_commission_or_ce(self):
        case_a, _pr_a = self._case_on(self.child_a)
        case_b, _pr_b = self._case_on(self.child_b)
        _pr, envelope_a = self._ce_pending_on(self.child_a)
        _pr, envelope_b = self._ce_pending_on(self.child_b)

        Case = self._as_user(self.user_child_a_cm, 'zvy.commission.case')
        self.assertIn(case_a, Case.search([('id', 'in', [case_a.id, case_b.id])]))
        self.assertNotIn(case_b, Case.search([('id', '=', case_b.id)]))
        with self.assertRaises(AccessError):
            Case.browse(case_b.id).check_access('read')

        Envelope = self._as_user(self.user_child_a_cce, 'zvy.closed.envelope')
        self.assertIn(
            envelope_a,
            Envelope.search([('id', 'in', [envelope_a.id, envelope_b.id])]),
        )
        self.assertNotIn(envelope_b, Envelope.search([('id', '=', envelope_b.id)]))
        with self.assertRaises(AccessError):
            Envelope.browse(envelope_b.id).check_access('read')

    def test_holding_commercial_manager_does_not_see_subsidiary_prs(self):
        pr_a = self._pr_on(self.child_a)
        Request = self._as_user(self.user_holding_cm, 'zvy.purchase.request')
        self.assertFalse(Request.search([('id', '=', pr_a.id)]))
        with self.assertRaises(AccessError):
            Request.browse(pr_a.id).check_access('read')

    def test_holding_settings_apply_child_flag_ignored(self):
        self.holding.zvy_commission_notice_days = 999
        self.child_a.zvy_commission_notice_days = 0
        self.holding.zvy_commission_require_comparison = True
        self.child_a.zvy_commission_require_comparison = False

        case, pr = self._case_on(self.child_a)
        result, _message = case._precheck_notice_window()
        self.assertEqual(result, 'fail')
        self.assertTrue(pr.commission_require_comparison)
        dossier, _msg = case._precheck_dossier()
        self.assertEqual(dossier, 'fail')

        self.holding.zvy_commission_notice_days = 0
        self.holding.zvy_commission_require_comparison = False
        self.child_a.zvy_commission_notice_days = 999
        self.child_a.zvy_commission_require_comparison = True
        pr.invalidate_recordset(['commission_require_comparison'])
        self.assertFalse(pr.commission_require_comparison)
        result, _message = case._precheck_notice_window()
        self.assertEqual(result, 'pass')
        dossier, _msg = case._precheck_dossier()
        self.assertEqual(dossier, 'pass')

        settings = self.env['res.config.settings'].with_company(self.child_a).create({
            'company_id': self.child_a.id,
        })
        self.assertFalse(settings.zvy_is_holding_company)
        self.assertEqual(settings.zvy_commission_notice_days, 0)
        holding_settings = self.env['res.config.settings'].with_company(
            self.holding
        ).create({'company_id': self.holding.id})
        self.assertTrue(holding_settings.zvy_is_holding_company)

    def test_subsidiary_need_commission_overlay_rejected(self):
        Overlay = self.env['zvy.product.procurement.company']
        Overlay.create({
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'company_id': self.holding.id,
            'override_need_commission': True,
            'need_commission': True,
        })
        pr = self._pr_on(self.child_a)
        self.assertTrue(pr.line_ids.is_commission_item)
        with self.assertRaises(ValidationError):
            Overlay.create({
                'product_tmpl_id': self.product.product_tmpl_id.id,
                'company_id': self.child_a.id,
                'override_need_commission': True,
                'need_commission': True,
            })
