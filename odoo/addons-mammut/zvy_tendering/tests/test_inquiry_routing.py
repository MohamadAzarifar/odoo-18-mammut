# -*- coding: utf-8 -*-
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

    def test_quote_set_on_request_editable_by_cm_only(self):
        pr = self._submit_and_assign(experts=self.user_cce)
        self.assertFalse(pr.with_user(self.user_cce).can_edit_quotes)

        cm_pr = pr.with_user(self.user_cm).with_company(self.company_a)
        self.assertTrue(cm_pr.can_edit_quotes)
        cm_pr.write({
            'quote_ids': [(0, 0, {
                'line_id': pr.line_ids[0].id,
                'partner_id': self.partner_a.id,
                'price_unit': 20.0,
            })],
        })
        self.assertEqual(len(pr.quote_ids), 1)

        # Header content on the PR is still locked outside draft/correction.
        with self.assertRaises(UserError):
            cm_pr.write({'description': 'changed'})

    def test_quote_vendor_selection_limited_to_avl(self):
        pr = self._submit_and_assign()
        quote = self.env['zvy.quote'].with_user(self.user_cce).with_company(
            self.company_a
        ).new({'line_id': pr.line_ids[0].id})

        allowed = quote.allowed_partner_ids._origin
        self.assertIn(self.partner_a, allowed)
        self.assertNotIn(self.partner_non_avl, allowed)
        # partner_b is on company A's AVL too; company B-only entries stay out.
        self.assertIn(self.partner_b, allowed)

        # Without a line there is nothing to scope the AVL by.
        self.assertFalse(
            self.env['zvy.quote'].with_user(self.user_cce).new({}).allowed_partner_ids
        )

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

    def test_sole_source_allows_one_quote(self):
        self._ensure_sole_source_avl()
        pr = self._create_draft_pr(line_vals=[{
            'product_id': self.product.id,
            'product_uom_qty': 1.0,
            'product_uom_id': self.product.uom_id.id,
            'price_estimate': 20.0,
        }])
        self.assertTrue(pr.line_ids.sole_source)
        pr = self._submit_and_assign(pr=pr)
        self._add_quotes(pr, count=1)
        pr.with_user(self.user_cce).action_submit_quotes()
        self.assertEqual(pr.state, 'quote_review')

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

    def test_line_flags_computed_from_avl_and_product(self):
        """Sole source / commission are derived; not settable by the planner."""
        pr = self._create_draft_pr()
        line = pr.line_ids
        self.assertFalse(line.sole_source)
        self.assertFalse(line.is_commission_item)

        self._ensure_sole_source_avl()
        self.assertTrue(line.sole_source)

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
        self.company_a.zvy_high_value_threshold = 100000.0
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

    def test_router_high_value_creates_commission_case(self):
        self.company_a.zvy_high_value_threshold = 50.0
        pr = self._submit_and_assign()
        self.assertTrue(pr.is_high_value)
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        self._award_quotes(pr)
        pr.with_user(self.user_cm).action_approve_quotes()
        self.assertEqual(pr.state, 'commission')
        self.assertTrue(pr.commission_case_id)
        self.assertTrue(pr.commission_case_id.reason_high_value)
        self.assertTrue(pr.commission_case_id.name.startswith('CASE/'))

    def test_router_commission_item_creates_case(self):
        self.company_a.zvy_high_value_threshold = 100000.0
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
        self.assertEqual(pr.state, 'commission')
        self.assertTrue(pr.commission_case_id.reason_commission_item)

    def test_approve_quotes_requires_award(self):
        self.company_a.zvy_high_value_threshold = 100000.0
        pr = self._submit_and_assign()
        self._add_quotes(pr)
        pr.with_user(self.user_cce).action_submit_quotes()
        with self.assertRaises(ValidationError):
            pr.with_user(self.user_cm).action_approve_quotes()

    def test_cm_can_set_awarded_quote_via_pr_form(self):
        """UI saves awarded quotes through parent line_ids write (quote_review)."""
        self.company_a.zvy_high_value_threshold = 100000.0
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
        self.company_a.zvy_high_value_threshold = 100000.0
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
        siblings = quotes - first
        self.assertTrue(all(q.state == 'rejected' for q in siblings))

        second.with_user(self.user_cm).action_select_as_awarded()
        self.assertEqual(line.awarded_quote_id, second)
        self.assertEqual(second.state, 'submitted')
        self.assertEqual(first.state, 'rejected')
        self.assertFalse(first.is_awarded)

        with self.assertRaises(UserError):
            first.with_user(self.user_planner).action_select_as_awarded()
