# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyPortalIsolation(ZvyTenderingCommon):

    def _create_portal_open_ce(self, deadline_hours=24, opening_offset_hours=1):
        pr = self._submit_and_assign(pr=self._create_draft_pr(line_vals=[{
            'product_id': self.product_tendering.id,
            'product_uom_qty': 2.0,
            'product_uom_id': self.product_tendering.uom_id.id,
            'price_estimate': 50.0,
        }]))
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
            'bid_deadline': opening + timedelta(hours=deadline_hours),
        })
        envelope.with_user(self.user_comm_mgr).action_approve_list()
        self.assertEqual(envelope.state, 'portal_open')
        return pr, envelope

    def test_portal_isolation_invited_vs_not(self):
        _pr, envelope = self._create_portal_open_ce()
        Envelope = self.env['zvy.closed.envelope']

        invited = Envelope.with_user(self.user_portal_a).search(
            Envelope._get_portal_domain(self.user_portal_a)
        )
        self.assertIn(envelope, invited)

        outsider = Envelope.with_user(self.user_portal_outsider).search(
            Envelope._get_portal_domain(self.user_portal_outsider)
        )
        self.assertNotIn(envelope, outsider)

        # Record rule: non-invited cannot read the CE
        with self.assertRaises(AccessError):
            envelope.with_user(self.user_portal_outsider).check_access('read')

        # Invited can read
        envelope.with_user(self.user_portal_a).check_access('read')

    def test_portal_amount_preview_format_and_words(self):
        _pr, envelope = self._create_portal_open_ce()
        empty = envelope._portal_amount_preview(0)
        self.assertEqual(empty['formatted'], '')
        self.assertEqual(empty['words'], '')

        preview = envelope._portal_amount_preview(1500.5)
        self.assertTrue(preview['formatted'])
        self.assertTrue(preview['words'])
        self.assertIn('1', preview['formatted'])

        fa_preview = envelope.with_context(lang='fa_IR')._portal_amount_preview(1234)
        self.assertTrue(fa_preview['formatted'])
        self.assertTrue(fa_preview['words'])
        # Persian digits-to-words should contain Persian letters when num2fawords is available
        try:
            import num2fawords  # noqa: F401
        except ImportError:
            self.skipTest('num2fawords not installed')
        self.assertRegex(fa_preview['words'], r'[\u0600-\u06FF]')

        irr = self.env.ref('base.IRR')
        self.assertEqual(irr.currency_unit_label, 'Rial')
        unit, _subunit = envelope._currency_amount_labels(irr)
        self.assertEqual(unit, 'Rial')
        irr_words = envelope.with_context(lang='fa_IR')._amount_to_persian_words(1500, irr)
        self.assertTrue(
            irr_words.endswith('ریال') or irr_words.endswith('Rial'),
            irr_words,
        )
        self.assertFalse(
            irr_words.endswith('دینار') or irr_words.endswith('Dinar'),
            irr_words,
        )

    def test_portal_bid_seal_other_supplier(self):
        _pr, envelope = self._create_portal_open_ce()
        Bid = self.env['zvy.closed.envelope.bid']
        bid = Bid._portal_upsert_bid(
            envelope, self.partner_a_contact, 1500.0, notes='secret-a'
        )
        self.assertEqual(bid.source, 'portal')
        self.assertEqual(bid.partner_id, self.partner_a)

        # Own portal user sees amount
        own = bid.with_user(self.user_portal_a).read(['amount', 'notes'])[0]
        self.assertEqual(own['amount'], 1500.0)
        self.assertEqual(own['notes'], 'secret-a')

        # Other invited supplier cannot see this bid (own-partner rule)
        other_bids = Bid.with_user(self.user_portal_b).search([
            ('envelope_id', '=', envelope.id),
        ])
        self.assertFalse(other_bids)

        # Internal non-manager still sealed until open
        sealed = bid.with_user(self.user_cce).read(['amount', 'notes'])[0]
        self.assertEqual(sealed['amount'], 0.0)
        self.assertFalse(sealed['notes'])

    def test_portal_deadline_and_withdraw(self):
        _pr, envelope = self._create_portal_open_ce(deadline_hours=24)
        Bid = self.env['zvy.closed.envelope.bid']

        bid = Bid._portal_upsert_bid(envelope, self.partner_a_contact, 100.0)
        self.assertTrue(bid.exists())

        # Update while open
        Bid._portal_upsert_bid(envelope, self.partner_a_contact, 200.0, notes='updated')
        self.assertEqual(bid.amount, 200.0)

        Bid._portal_withdraw_bid(envelope, self.partner_a_contact)
        self.assertFalse(bid.exists())

        # Past deadline → reject
        envelope.sudo().write({
            'bid_deadline': fields.Datetime.now() - timedelta(minutes=1),
        })
        with self.assertRaises(UserError):
            Bid._portal_upsert_bid(envelope, self.partner_a_contact, 300.0)

        # Re-open deadline, submit, then open bids → reject updates
        envelope.sudo().write({
            'bid_deadline': fields.Datetime.now() + timedelta(hours=2),
            'opening_datetime': fields.Datetime.now() - timedelta(minutes=1),
        })
        Bid._portal_upsert_bid(envelope, self.partner_a_contact, 400.0)
        envelope.with_user(self.user_comm_mgr).action_open_bids()
        with self.assertRaises(UserError):
            Bid._portal_upsert_bid(envelope, self.partner_a_contact, 500.0)
        with self.assertRaises(UserError):
            Bid._portal_withdraw_bid(envelope, self.partner_a_contact)

    def test_portal_notifications_on_open_result_clarification(self):
        Mail = self.env['mail.mail'].sudo()
        before = Mail.search_count([])

        _pr, envelope = self._create_portal_open_ce()
        invite_mails = Mail.search([
            ('model', '=', 'zvy.closed.envelope'),
            ('res_id', '=', envelope.id),
        ])
        self.assertGreaterEqual(len(invite_mails), 1)

        envelope.with_user(self.user_comm_mgr)._post_clarification('Please confirm lead time.')
        clar_mails = Mail.search([
            ('model', '=', 'zvy.closed.envelope'),
            ('res_id', '=', envelope.id),
            ('subject', 'ilike', 'Clarification'),
        ])
        self.assertTrue(clar_mails)

        Bid = self.env['zvy.closed.envelope.bid']
        Bid._portal_upsert_bid(envelope, self.partner_a_contact, 111.0)
        envelope.sudo().write({
            'opening_datetime': fields.Datetime.now() - timedelta(minutes=1),
        })
        envelope.with_user(self.user_comm_mgr).action_open_bids()
        envelope.with_user(self.user_comm_mgr).write({
            'winner_partner_id': self.partner_a.id,
        })
        envelope.with_user(self.user_comm_mgr).action_select_winner()
        awarded = Mail.search([
            ('model', '=', 'zvy.closed.envelope'),
            ('res_id', '=', envelope.id),
            ('subject', 'ilike', 'awarded'),
        ])
        not_awarded = Mail.search([
            ('model', '=', 'zvy.closed.envelope'),
            ('res_id', '=', envelope.id),
            ('subject', 'ilike', 'Result for tender'),
        ])
        self.assertTrue(awarded)
        self.assertTrue(not_awarded)

        _pr2, envelope2 = self._create_portal_open_ce()
        envelope2.with_user(self.user_comm_mgr).action_cancel()
        cancelled = Mail.search([
            ('model', '=', 'zvy.closed.envelope'),
            ('res_id', '=', envelope2.id),
            ('subject', 'ilike', 'cancelled'),
        ])
        self.assertTrue(cancelled)
        self.assertGreaterEqual(Mail.search_count([]), before)
