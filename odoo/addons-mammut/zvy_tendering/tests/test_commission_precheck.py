# -*- coding: utf-8 -*-
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyCommissionPrecheck(ZvyTenderingCommon):

    def _route_to_signatory(self, award_partner=None, award_reason=None):
        self._force_large_bands()
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        if award_reason:
            partner = award_partner or self.partner_c
            for line in pr.sudo().line_ids:
                quote = line.quote_ids.filtered(
                    lambda q: q.state == 'submitted' and q.partner_id == partner
                )[:1]
                line.with_user(self.user_cm).write({
                    'awarded_quote_id': quote.id,
                    'award_not_lowest_reason': award_reason,
                })
        else:
            self._award_quotes(pr, partner=award_partner)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        return pr

    def _assert_returned_to_cm(self, pr, case, check_sequence):
        self.assertEqual(pr.state, 'cm_review')
        case = case.sudo()
        self.assertEqual(case.state, 'returned')
        self.assertTrue(case.precheck_failed)
        row = case.precheck_ids.filtered(lambda r: r.sequence == check_sequence)
        self.assertEqual(row.result, 'fail')
        messages = self.env['mail.message'].sudo().search([
            ('model', '=', 'zvy.purchase.request'),
            ('res_id', '=', pr.id),
        ])
        self.assertTrue(
            any(('Check %s' % check_sequence) in (m.body or '') for m in messages),
            'Expected a system comment mentioning check %s' % check_sequence,
        )

    def test_all_green_checks_leave_case_open(self):
        pr = self._route_to_signatory()
        self._approve_all_signatories(pr, expected_state='commission')
        case = pr.sudo().commission_case_id
        self.assertEqual(case.state, 'open')
        self.assertFalse(case.precheck_failed)
        self.assertEqual(len(case.precheck_ids), 10)
        self.assertEqual(
            set(case.precheck_ids.mapped('result')),
            {'pass', 'skipped'},
        )

    def test_missing_non_lowest_reason_returns_to_cm(self):
        pr = self._route_to_signatory(award_reason='Better quality')
        pr.line_ids.sudo().write({'award_not_lowest_reason': False})
        self._approve_all_signatories(pr, expected_state='cm_review')
        self._assert_returned_to_cm(pr, pr.sudo().commission_case_id, 8)

    def test_non_avl_vendor_returns_to_cm(self):
        pr = self._route_to_signatory()
        self.avl_a.sudo().write({'active': False})
        self._approve_all_signatories(pr, expected_state='cm_review')
        self._assert_returned_to_cm(pr, pr.sudo().commission_case_id, 6)

    def test_incomplete_signatory_chain_fails_check_9(self):
        pr = self._route_to_signatory()
        case = pr._action_open_commission_case()
        self._assert_returned_to_cm(pr, case, 9)
        self.assertNotEqual(pr.state, 'commission')

    def test_sap_stubs_do_not_fail(self):
        pr = self._route_to_signatory()
        self._approve_all_signatories(pr, expected_state='commission')
        case = pr.sudo().commission_case_id
        by_seq = {row.sequence: row for row in case.precheck_ids}
        self.assertEqual(by_seq[3].result, 'skipped')
        self.assertEqual(by_seq[10].result, 'skipped')
        self.assertNotEqual(by_seq[3].result, 'fail')
        self.assertNotEqual(by_seq[10].result, 'fail')

    def test_missing_proforma_fails_when_required(self):
        self.company_a.zvy_commission_require_proforma = True
        pr = self._route_to_signatory()
        self._approve_all_signatories(pr, expected_state='cm_review')
        self._assert_returned_to_cm(pr, pr.sudo().commission_case_id, 5)

    def test_notice_window_fails_when_configured(self):
        self.company_a.zvy_commission_notice_days = 999
        pr = self._route_to_signatory()
        self._approve_all_signatories(pr, expected_state='cm_review')
        self._assert_returned_to_cm(pr, pr.sudo().commission_case_id, 1)
