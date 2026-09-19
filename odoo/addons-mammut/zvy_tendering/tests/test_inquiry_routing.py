# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import ZvyTenderingCommon


@tagged('post_install', '-at_install')
class TestZvyInquiryRouting(ZvyTenderingCommon):

    def test_expert_cannot_edit_unassigned_lines_or_quotes(self):
        pr = self._submit_and_assign(experts=self.user_cce)
        line = pr.line_ids[0]

        with self.assertRaises(AccessError):
            self.env['zvy.purchase.request.line'].with_user(self.user_cce_other).browse(
                line.id
            ).read(['product_id'])

        try:
            self.env['zvy.quote'].with_user(self.user_cce_other).with_company(
                self.company_a
            ).create({
                'line_id': line.id,
                'partner_id': self.partner_a.id,
                'price_unit': 12.0,
            })
        except (AccessError, UserError):
            pass
        else:
            self.fail('Unassigned expert should not create quotes on this line')

        # Assigned expert can create a quote.
        quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(
            self.company_a
        ).create({
            'line_id': line.id,
            'partner_id': self.partner_a.id,
            'price_unit': 12.0,
        })
        self.assertEqual(quote.state, 'draft')

        # Content edit on line still blocked outside draft/correction.
        with self.assertRaises(UserError):
            line.with_user(self.user_cce).write({'product_uom_qty': 99.0})

    def test_expert_cannot_set_recorded_by_or_state(self):
        pr = self._submit_and_assign(experts=self.user_cce)
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)

        quote = Quote.create({
            'line_id': pr.line_ids[0].id,
            'partner_id': self.partner_a.id,
            'price_unit': 10.0,
            'expert_user_id': self.user_cm.id,
            'state': 'accepted',
        })
        self.assertEqual(quote.expert_user_id, self.user_cce)
        self.assertEqual(quote.state, 'draft')

        with self.assertRaises(UserError):
            quote.write({'state': 'submitted'})
        with self.assertRaises(UserError):
            quote.write({'expert_user_id': self.user_cm.id})

    def test_expert_adds_quote_through_line(self):
        """The line form saves quotes as a one2many command on the line itself."""
        pr = self._submit_and_assign(experts=self.user_cce)
        line = pr.line_ids[0].with_user(self.user_cce).with_company(self.company_a)

        line.write({
            'quote_ids': [(0, 0, {
                'partner_id': self.partner_a.id,
                'price_unit': 15.0,
            })],
        })
        self.assertEqual(len(line.quote_ids), 1)
        self.assertEqual(line.quote_ids.request_id, pr)

        # Other line content stays locked outside draft/correction.
        with self.assertRaises(UserError):
            line.write({'product_uom_qty': 5.0})

    def test_cm_adds_quote_through_line(self):
        """CM records quotes from the line in inquiry; PR header stays locked."""
        pr = self._submit_and_assign(experts=self.user_cce)
        line = pr.line_ids[0].with_user(self.user_cm).with_company(self.company_a)
        line.write({
            'quote_ids': [(0, 0, {
                'partner_id': self.partner_a.id,
                'price_unit': 20.0,
            })],
        })
        self.assertEqual(len(pr.quote_ids), 1)

        with self.assertRaises(UserError):
            pr.with_user(self.user_cm).with_company(self.company_a).write(
                {'description': 'changed'}
            )

    def test_action_view_quotes_opens_line_quotes(self):
        pr = self._submit_and_assign(experts=self.user_cce)
        line = pr.line_ids[0]
        action = line.action_view_quotes()
        form_view = self.env.ref('zvy_tendering.view_zvy_purchase_request_line_form')
        self.assertEqual(action['res_model'], 'zvy.purchase.request.line')
        self.assertEqual(action['res_id'], line.id)
        self.assertEqual(action['view_mode'], 'form')
        self.assertEqual(action['views'], [(form_view.id, 'form')])

    def test_quote_vendor_selection_limited_to_avl(self):
        pr = self._submit_and_assign()
        quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(
            self.company_a
        ).new({'line_id': pr.line_ids[0].id})

        allowed = quote.allowed_partner_ids._origin
        self.assertIn(self.partner_a, allowed)
        self.assertNotIn(self.partner_non_avl, allowed)
        self.assertIn(self.partner_b, allowed)

        # Without a line there is nothing to scope the AVL by.
        self.assertFalse(
            self.env['zvy.quote'].with_user(self.user_cce).new({}).allowed_partner_ids
        )

        pr_b = self.env['zvy.purchase.request'].create({
            'company_id': self.company_b.id,
            'requester_id': self.user_planner.id,
            'description': 'Company B PR uses the same AVL',
            'line_ids': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 10.0,
            })],
        })
        quote_b = self.env['zvy.quote'].new({'line_id': pr_b.line_ids[0].id})
        self.assertIn(self.partner_a, quote_b.allowed_partner_ids._origin)

    def test_non_avl_partner_rejected_on_quote(self):
        pr = self._submit_and_assign()
        with self.assertRaises(ValidationError):
            self.env['zvy.quote'].with_user(self.user_cce).with_company(
                self.company_a
            ).create({
                'line_id': pr.line_ids[0].id,
                'partner_id': self.partner_non_avl.id,
                'price_unit': 10.0,
            })

    def test_split_assignment_submits_per_line(self):
        """Two experts, one line each: PR advances only when both submit."""
        pr = self._create_draft_pr(line_vals=[
            {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 10.0,
            },
            {
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 20.0,
            },
        ])
        pr.action_submit()
        line_a, line_b = pr.line_ids
        pr.with_user(self.user_cm)._action_assign_experts({
            line_a.id: [self.user_cce.id],
            line_b.id: [self.user_cce_other.id],
        })

        for line, expert in ((line_a, self.user_cce), (line_b, self.user_cce_other)):
            Quote = self.env['zvy.quote'].with_user(expert).with_company(self.company_a)
            for partner in (self.partner_a, self.partner_b, self.partner_c):
                Quote.create({
                    'line_id': line.id,
                    'partner_id': partner.id,
                    'price_unit': 10.0,
                })

        # Expert A submits only their own line; the PR must stay in inquiry.
        line_a.with_user(self.user_cce).action_submit_quotes()
        self.assertTrue(line_a.quotes_submitted)
        self.assertFalse(line_b.quotes_submitted)
        self.assertEqual(pr.state, 'inquiry')

        # Expert A cannot submit the line assigned to someone else.
        try:
            line_b.with_user(self.user_cce).action_submit_quotes()
        except (UserError, AccessError):
            pass
        else:
            self.fail('Expert must not submit a line assigned to another expert')

        line_b.with_user(self.user_cce_other).action_submit_quotes()
        self.assertEqual(pr.state, 'quote_review')
        self.assertTrue(all(q.state == 'submitted' for q in pr.sudo().quote_ids))

    def test_expert_submits_partial_assignment_from_request(self):
        """Request-level submit only touches the caller's own lines (no AccessError)."""
        pr = self._create_draft_pr(line_vals=[
            {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 10.0,
            },
            {
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 20.0,
            },
        ])
        pr.action_submit()
        line_a, line_b = pr.line_ids
        pr.with_user(self.user_cm)._action_assign_experts({
            line_a.id: [self.user_cce.id],
            line_b.id: [self.user_cce_other.id],
        })
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        for partner in (self.partner_a, self.partner_b, self.partner_c):
            Quote.create({
                'line_id': line_a.id,
                'partner_id': partner.id,
                'price_unit': 10.0,
            })

        pr.with_user(self.user_cce).action_submit_quotes()
        self.assertTrue(line_a.quotes_submitted)
        self.assertFalse(line_b.quotes_submitted)
        self.assertEqual(pr.state, 'inquiry')

    def test_cm_cannot_submit_quotes(self):
        pr = self._submit_and_assign(experts=self.user_cce)
        self._add_quotes(pr)
        with self.assertRaises(UserError):
            pr.with_user(self.user_cm).action_submit_quotes()
        self.assertEqual(pr.state, 'inquiry')

    def test_quote_minima_block_and_allow_submit(self):
        pr = self._submit_and_assign()
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        line = pr.line_ids[0]

        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_a.id,
            'price_unit': 10.0,
        })
        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_b.id,
            'price_unit': 11.0,
        })
        with self.assertRaises(ValidationError):
            pr.with_user(self.user_cce).action_submit_quotes()

        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_c.id,
            'price_unit': 12.0,
        })
        pr.with_user(self.user_cce).action_submit_quotes()
        self.assertEqual(pr.state, 'quote_review')
        self.assertTrue(all(q.state == 'submitted' for q in pr.sudo().quote_ids))

    def test_quote_shortfall_reason_allows_submit(self):
        pr = self._submit_and_assign()
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        line = pr.line_ids[0]
        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_a.id,
            'price_unit': 10.0,
        })
        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_b.id,
            'price_unit': 11.0,
        })
        line.sudo().write({
            'quote_shortfall_reason': 'Only two AVL vendors responded',
        })
        pr.with_user(self.user_cce).action_submit_quotes()
        self.assertEqual(pr.state, 'quote_review')
        self.assertEqual(
            line.quote_shortfall_reason,
            'Only two AVL vendors responded',
        )
        self.assertTrue(all(q.state == 'submitted' for q in pr.sudo().quote_ids))

    def test_quote_shortfall_zero_quotes_still_blocked(self):
        pr = self._submit_and_assign()
        line = pr.line_ids[0]
        line.sudo().write({
            'quote_shortfall_reason': 'No vendors available',
        })
        with self.assertRaises(ValidationError):
            pr.with_user(self.user_cce).action_submit_quotes()
        self.assertEqual(pr.state, 'inquiry')

    def test_quote_shortfall_ui_opens_wizard(self):
        pr = self._submit_and_assign()
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        line = pr.line_ids[0]
        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_a.id,
            'price_unit': 10.0,
        })
        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_b.id,
            'price_unit': 11.0,
        })
        action = pr.with_user(self.user_cce).with_context(
            zvy_ui_submit=True,
        ).action_submit_quotes()
        self.assertEqual(action['res_model'], 'zvy.request.quote.shortfall.wizard')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(pr.state, 'inquiry')

        wizard = self.env['zvy.request.quote.shortfall.wizard'].with_user(
            self.user_cce
        ).create({
            'line_ids': [(6, 0, line.ids)],
            'reason': 'Only two AVL vendors responded',
        })
        wizard.action_confirm()
        self.assertEqual(pr.state, 'quote_review')
        self.assertEqual(
            line.quote_shortfall_reason,
            'Only two AVL vendors responded',
        )

    def test_line_commission_flag_from_product(self):
        """Commission item is derived from the product; not settable by the planner."""
        pr = self._create_draft_pr()
        self.assertFalse(pr.line_ids.is_commission_item)

        pr_comm = self._create_draft_pr(line_vals=[{
            'product_id': self.product_commission.id,
            'product_uom_qty': 1.0,
            'product_uom_id': self.product_commission.uom_id.id,
            'price_estimate': 10.0,
        }])
        self.assertTrue(pr_comm.line_ids.is_commission_item)
        self.assertTrue(pr_comm.is_commission_item)

    def test_cm_reject_quotes_returns_to_inquiry(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()

        with self.assertRaises(ValidationError):
            pr.with_user(self.user_cm)._action_reject_quotes('   ')

        pr.with_user(self.user_cm)._action_reject_quotes('Prices too high')
        self.assertEqual(pr.state, 'inquiry')
        self.assertEqual(pr.quote_reject_reason, 'Prices too high')
        self.assertTrue(all(q.state == 'draft' for q in pr.sudo().quote_ids))

    def test_router_company_path_signatory_stub(self):
        pr = self._submit_and_assign()
        self.assertFalse(pr.is_high_value)
        self.assertFalse(pr.is_commission_item)
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        self.assertTrue(pr.sudo().approval_request_id)
        self.assertEqual(pr.sudo().approval_request_id.request_status, 'pending')
        self.assertFalse(pr.commission_case_id)
        self._approve_all_signatories(pr)
        self.assertEqual(pr.state, 'po_ready')
        self.assertFalse(pr.commission_case_id)

    def test_router_high_value_creates_commission_case(self):
        self._force_large_bands()
        pr = self._submit_and_assign()
        self.assertTrue(pr.is_high_value)
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        self.assertFalse(pr.commission_case_id)
        self._approve_all_signatories(pr, expected_state='commission')
        self.assertEqual(pr.state, 'commission')
        self.assertTrue(pr.commission_case_id)
        self.assertTrue(pr.commission_case_id.reason_high_value)
        self.assertTrue(pr.commission_case_id.name.startswith('CASE/'))

    def test_router_commission_item_creates_case(self):
        pr = self._create_draft_pr(line_vals=[{
            'product_id': self.product_commission.id,
            'product_uom_qty': 1.0,
            'product_uom_id': self.product_commission.uom_id.id,
            'price_estimate': 10.0,
        }])
        pr = self._submit_and_assign(pr=pr)
        self.assertTrue(pr.is_commission_item)
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

    def test_enquiry_cannot_enter_commission_without_approved_chain(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')
        with self.assertRaises(UserError):
            pr.sudo().write({'state': 'commission'})

    def test_approve_quotes_requires_award(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        with self.assertRaises(ValidationError):
            pr.with_user(self.user_cm).action_approve_quotes()

    def test_cm_can_set_awarded_quote_via_pr_form(self):
        """UI saves awarded quotes through parent line_ids write (quote_review)."""
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self.assertEqual(pr.state, 'quote_review')
        line = pr.line_ids[:1]
        quote = line.quote_ids.filtered(lambda q: q.state == 'submitted')[:1]
        pr.with_user(self.user_cm).write({
            'line_ids': [(1, line.id, {'awarded_quote_id': quote.id})],
        })
        self.assertEqual(line.awarded_quote_id, quote)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'signatory')

    def test_select_as_awarded_rejects_siblings_and_display_name(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        line = pr.line_ids[:1]
        quotes = line.quote_ids.filtered(lambda q: q.state == 'submitted')
        self.assertGreaterEqual(len(quotes), 2)
        first, second = quotes[0], quotes[1]

        self.assertIn(first.partner_id.name, first.display_name)

        first.with_user(self.user_cm).action_select_as_awarded()
        self.assertEqual(line.awarded_quote_id, first)
        self.assertEqual(first.state, 'submitted')
        self.assertTrue(first.is_awarded)
        self.assertFalse(line.award_not_lowest_reason)
        siblings = quotes - first
        self.assertTrue(all(q.state == 'rejected' for q in siblings))

        with self.assertRaises(ValidationError):
            second.with_user(self.user_cm).action_select_as_awarded()

        second.with_user(self.user_cm).with_context(
            zvy_award_not_lowest_reason='Better quality',
        ).action_select_as_awarded()
        self.assertEqual(line.awarded_quote_id, second)
        self.assertEqual(second.state, 'submitted')
        self.assertEqual(first.state, 'rejected')
        self.assertFalse(first.is_awarded)
        self.assertEqual(line.award_not_lowest_reason, 'Better quality')

        with self.assertRaises(UserError):
            first.with_user(self.user_planner).action_select_as_awarded()

    def test_award_not_lowest_requires_reason_on_write_and_ui(self):
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        line = pr.line_ids[:1]
        quotes = line.quote_ids.filtered(lambda q: q.state == 'submitted').sorted(
            'price_unit'
        )
        lowest, higher = quotes[0], quotes[1]
        self.assertGreater(higher.price_unit, lowest.price_unit)

        with self.assertRaises(ValidationError):
            line.with_user(self.user_cm).write({'awarded_quote_id': higher.id})

        line.with_user(self.user_cm).write({
            'awarded_quote_id': higher.id,
            'award_not_lowest_reason': 'Shorter lead time',
        })
        self.assertEqual(line.awarded_quote_id, higher)
        self.assertEqual(line.award_not_lowest_reason, 'Shorter lead time')

        line.with_user(self.user_cm).write({'awarded_quote_id': lowest.id})
        self.assertEqual(line.awarded_quote_id, lowest)
        self.assertFalse(line.award_not_lowest_reason)

        action = higher.with_user(self.user_cm).with_context(
            zvy_ui_award=True,
        ).action_select_as_awarded()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'zvy.request.award.not.lowest.wizard')

        wizard = self.env['zvy.request.award.not.lowest.wizard'].with_user(
            self.user_cm
        ).create({
            'quote_id': higher.id,
            'reason': 'Better warranty',
        })
        wizard.action_confirm()
        self.assertEqual(line.awarded_quote_id, higher)
        self.assertEqual(line.award_not_lowest_reason, 'Better warranty')

    def test_priced_quote_computes_total_unpriced_excluded(self):
        pr = self._submit_and_assign()
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        line = pr.line_ids[0]
        priced = Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_a.id,
            'price_unit': 10.0,
        })
        self.assertEqual(priced.amount_total, 10.0 * line.product_uom_qty)
        self.assertTrue(priced.is_valid_inquiry)

        with self.assertRaises(ValidationError):
            Quote.create({
                'line_id': line.id,
                'partner_id': self.partner_b.id,
                'price_unit': 0.0,
            })

        unpriced = Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_b.id,
            'price_unit': 0.0,
            'comments': 'Waiting on written offer',
        })
        self.assertEqual(unpriced.amount_total, 0.0)
        self.assertFalse(unpriced.is_valid_inquiry)
        self.assertEqual(line._valid_inquiry_count(), 1)

    def test_no_price_obtained_requires_comments_and_clears_unit(self):
        pr = self._submit_and_assign()
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        line = pr.line_ids[0]

        with self.assertRaises(ValidationError):
            Quote.create({
                'line_id': line.id,
                'partner_id': self.partner_a.id,
                'no_price_obtained': True,
                'price_unit': 99.0,
            })

        unpriced = Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_a.id,
            'no_price_obtained': True,
            'price_unit': 99.0,
            'comments': 'Called supplier; no valid price yet',
        })
        self.assertTrue(unpriced.no_price_obtained)
        self.assertEqual(unpriced.price_unit, 0.0)
        self.assertFalse(unpriced.is_valid_inquiry)
        self.assertFalse(unpriced._is_priced())

        unpriced.write({'price_unit': 25.0})
        self.assertEqual(unpriced.price_unit, 0.0)

    def test_quote_contact_defaults_from_vendor_and_stays_editable(self):
        pr = self._submit_and_assign()
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        quote = Quote.create({
            'line_id': pr.line_ids[0].id,
            'partner_id': self.partner_a.id,
            'price_unit': 10.0,
        })
        self.assertEqual(quote.contact_name, self.partner_a.name)
        self.assertEqual(quote.contact_phone, self.partner_a.phone)
        quote.write({
            'contact_name': 'Plant buyer',
            'contact_phone': '+98 21 9999',
        })
        self.assertEqual(quote.contact_name, 'Plant buyer')
        self.assertEqual(quote.contact_phone, '+98 21 9999')

    def test_last_purchase_from_confirmed_po(self):
        po = self._create_confirmed_po(price=42.5)
        pr = self._create_draft_pr()
        line = pr.line_ids[0]
        self.assertEqual(line.last_vendor_id, self.partner_a)
        self.assertAlmostEqual(line.last_price, 42.5)
        self.assertTrue(line.last_purchase_date)
        expected = fields.Date.to_date(po.date_approve or po.date_order)
        self.assertEqual(line.last_purchase_date, expected)

    def test_last_purchase_empty_without_history(self):
        pr = self._create_draft_pr()
        line = pr.line_ids[0]
        self.assertFalse(line.last_vendor_id)
        self.assertFalse(line.last_price)
        self.assertFalse(line.last_purchase_date)

    def test_stale_quote_does_not_satisfy_minima(self):
        pr = self._submit_and_assign()
        quotes = self._add_quotes(pr, count=3)
        quotes[2].sudo().write({
            'received_date': fields.Datetime.now() - timedelta(days=31),
        })
        self.assertEqual(pr.line_ids._valid_inquiry_count(), 2)
        with self.assertRaises(ValidationError):
            pr.with_user(self.user_cce).action_submit_quotes()
        pr.line_ids.sudo().write({
            'quote_shortfall_reason': 'Third offer expired',
        })
        pr.with_user(self.user_cce).action_submit_quotes()
        self.assertEqual(pr.state, 'quote_review')

    def test_unpriced_quote_does_not_satisfy_minima(self):
        pr = self._submit_and_assign()
        Quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(self.company_a)
        line = pr.line_ids[0]
        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_a.id,
            'price_unit': 10.0,
        })
        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_b.id,
            'price_unit': 11.0,
        })
        Quote.create({
            'line_id': line.id,
            'partner_id': self.partner_c.id,
            'price_unit': 0.0,
            'comments': 'Price to follow in writing',
        })
        self.assertEqual(line._valid_inquiry_count(), 2)
        with self.assertRaises(ValidationError):
            pr.with_user(self.user_cce).action_submit_quotes()
