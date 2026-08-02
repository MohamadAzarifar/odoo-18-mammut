# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class ZvyTenderingCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env['res.company'].create({'name': 'ZVY Company A'})
        cls.company_b = cls.env['res.company'].create({'name': 'ZVY Company B'})
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'AVL Vendor A',
            'supplier_rank': 1,
            'email': 'vendor_a@example.com',
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'AVL Vendor B',
            'supplier_rank': 1,
            'email': 'vendor_b@example.com',
        })
        cls.partner_c = cls.env['res.partner'].create({
            'name': 'AVL Vendor C',
            'supplier_rank': 1,
            'email': 'vendor_c@example.com',
        })
        cls.partner_non_avl = cls.env['res.partner'].create({
            'name': 'Non AVL Vendor',
            'supplier_rank': 1,
            'email': 'non_avl@example.com',
        })
        cls.Avl = cls.env['zvy.avl.entry']
        cls.avl_a = cls.Avl.create({
            'partner_id': cls.partner_a.id,
            'company_id': cls.company_a.id,
        })
        cls.avl_b = cls.Avl.create({
            'partner_id': cls.partner_b.id,
            'company_id': cls.company_b.id,
        })
        cls.avl_a2 = cls.Avl.create({
            'partner_id': cls.partner_b.id,
            'company_id': cls.company_a.id,
        })
        cls.avl_a3 = cls.Avl.create({
            'partner_id': cls.partner_c.id,
            'company_id': cls.company_a.id,
        })
        cls.group_admin = cls.env.ref('zvy_tendering.group_zvy_tendering_admin')
        cls.group_planner = cls.env.ref('zvy_tendering.group_zvy_planner')
        cls.group_cm = cls.env.ref('zvy_tendering.group_zvy_commercial_manager')
        cls.group_cce = cls.env.ref('zvy_tendering.group_zvy_commercial_expert')
        cls.group_comm_mgr = cls.env.ref('zvy_tendering.group_zvy_commission_manager')
        cls.group_comm_exp = cls.env.ref('zvy_tendering.group_zvy_commission_expert')
        cls.user_company_a = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Admin Company A',
            'login': 'zvy_admin_company_a',
            'email': 'zvy_admin_a@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_admin.id,
            ])],
        })
        cls.product = cls.env['product.product'].create({
            'name': 'ZVY Test Product',
            'type': 'consu',
            'list_price': 100.0,
        })
        cls.commission_categ = cls.env['product.category'].create({
            'name': 'ZVY Commission Category',
            'zvy_is_commission_item': True,
        })
        cls.product_commission = cls.env['product.product'].create({
            'name': 'ZVY Commission Product',
            'type': 'consu',
            'list_price': 50.0,
            'categ_id': cls.commission_categ.id,
        })
        cls.user_planner = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Planner',
            'login': 'zvy_planner',
            'email': 'zvy_planner@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_planner.id,
            ])],
        })
        cls.user_planner_other = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Planner Other',
            'login': 'zvy_planner_other',
            'email': 'zvy_planner_other@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_planner.id,
            ])],
        })
        cls.user_cm = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Commercial Manager',
            'login': 'zvy_cm',
            'email': 'zvy_cm@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_cm.id,
            ])],
        })
        cls.user_cce = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Commercial Expert',
            'login': 'zvy_cce',
            'email': 'zvy_cce@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_cce.id,
            ])],
        })
        cls.user_cce_other = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Commercial Expert Other',
            'login': 'zvy_cce_other',
            'email': 'zvy_cce_other@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_cce.id,
            ])],
        })
        cls.user_comm_mgr = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Commission Manager',
            'login': 'zvy_comm_mgr',
            'email': 'zvy_comm_mgr@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_comm_mgr.id,
            ])],
        })
        cls.user_comm_exp = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Commission Expert',
            'login': 'zvy_comm_exp',
            'email': 'zvy_comm_exp@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_comm_exp.id,
            ])],
        })
        cls.user_bidder = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Bidder Partner A',
            'login': 'zvy_bidder_a',
            'email': 'zvy_bidder_a@example.com',
            'partner_id': cls.partner_a.id,
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_cce.id,
            ])],
        })
        cls.user_signatory = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Signatory',
            'login': 'zvy_signatory',
            'email': 'zvy_signatory@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('approvals.group_approval_user').id,
            ])],
        })
        cls.user_ceo = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY CEO',
            'login': 'zvy_ceo',
            'email': 'zvy_ceo@example.com',
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('approvals.group_approval_user').id,
            ])],
        })
        cls.signatory_category = cls.env['approval.category'].create({
            'name': 'ZVY Signatory Category',
            'company_id': cls.company_a.id,
            'approver_sequence': True,
            'approval_minimum': 1,
            'has_amount': 'optional',
            'has_reference': 'optional',
            'approver_ids': [(0, 0, {
                'user_id': cls.user_signatory.id,
                'required': True,
                'sequence': 10,
            })],
        })
        cls.company_a.zvy_signatory_approval_category_id = cls.signatory_category
        cls.company_a.zvy_sole_source_approver_ids = [(6, 0, [cls.user_ceo.id])]

        # Portal suppliers (true base.group_portal users on commercial child contacts)
        cls.partner_portal_outsider = cls.env['res.partner'].create({
            'name': 'Portal Outsider Vendor',
            'supplier_rank': 1,
            'email': 'outsider@example.com',
        })
        cls.partner_a_contact = cls.env['res.partner'].create({
            'name': 'Portal Contact A',
            'parent_id': cls.partner_a.id,
            'email': 'portal_contact_a@example.com',
            'type': 'contact',
        })
        cls.partner_b_contact = cls.env['res.partner'].create({
            'name': 'Portal Contact B',
            'parent_id': cls.partner_b.id,
            'email': 'portal_contact_b@example.com',
            'type': 'contact',
        })
        portal_group = cls.env.ref('base.group_portal')
        cls.user_portal_a = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Portal Vendor A',
            'login': 'zvy_portal_a',
            'email': 'zvy_portal_a@example.com',
            'partner_id': cls.partner_a_contact.id,
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [portal_group.id])],
        })
        cls.user_portal_b = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Portal Vendor B',
            'login': 'zvy_portal_b',
            'email': 'zvy_portal_b@example.com',
            'partner_id': cls.partner_b_contact.id,
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [portal_group.id])],
        })
        cls.user_portal_outsider = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZVY Portal Outsider',
            'login': 'zvy_portal_outsider',
            'email': 'zvy_portal_outsider@example.com',
            'partner_id': cls.partner_portal_outsider.id,
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
            'groups_id': [(6, 0, [portal_group.id])],
        })

    def _ensure_sole_source_avl(self, product=None, company=None, partner=None):
        """Leave exactly one active AVL vendor for product/company (sole source)."""
        product = product or self.product
        company = company or self.company_a
        partner = partner or self.partner_a
        self.Avl.search([('company_id', '=', company.id)]).write({'active': False})
        return self.Avl.create({
            'partner_id': partner.id,
            'company_id': company.id,
            'product_id': product.id,
        })

    def _create_draft_pr(self, user=None, company=None, **extra):
        user = user or self.user_planner
        company = company or self.company_a
        line_vals = extra.pop('line_vals', None)
        if line_vals is None:
            line_vals = [{
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'product_uom_id': self.product.uom_id.id,
                'price_estimate': 50.0,
            }]
        vals = {
            'company_id': company.id,
            'requester_id': user.id,
            'description': extra.pop('description', 'Test PR'),
            'line_ids': [(0, 0, line) for line in line_vals],
        }
        vals.update(extra)
        return self.env['zvy.purchase.request'].with_user(user).with_company(company).create(vals)

    def _submit_and_assign(self, pr=None, experts=None):
        """Create (optional), submit, and assign experts → inquiry."""
        pr = pr or self._create_draft_pr()
        if pr.state == 'draft':
            pr.action_submit()
        experts = experts or self.user_cce
        if hasattr(experts, 'ids'):
            expert_ids = experts.ids
        else:
            expert_ids = [experts.id]
        assignments = {line.id: expert_ids for line in pr.line_ids}
        pr.with_user(self.user_cm)._action_assign_experts(assignments)
        return pr

    def _add_quotes(self, pr, count=3, user=None, partners=None):
        """Add `count` AVL quotes on the first line (or all lines if sole source uses 1)."""
        user = user or self.user_cce
        partners = partners or [self.partner_a, self.partner_b, self.partner_c]
        Quote = self.env['zvy.quote'].with_user(user).with_company(pr.company_id)
        quotes = self.env['zvy.quote']
        for line in pr.line_ids:
            needed = 1 if line.sole_source else count
            for i in range(needed):
                partner = partners[i % len(partners)]
                quotes |= Quote.create({
                    'line_id': line.id,
                    'request_id': pr.id,
                    'partner_id': partner.id,
                    'price_unit': 10.0 + i,
                })
        return quotes

    def _award_quotes(self, pr, partner=None):
        """Select an awarded quote per line (defaults to first submitted quote)."""
        partner = partner or self.partner_a
        for line in pr.sudo().line_ids:
            quote = line.quote_ids.filtered(
                lambda q: q.state == 'submitted' and q.partner_id == partner
            )[:1]
            if not quote:
                quote = line.quote_ids.filtered(lambda q: q.state == 'submitted')[:1]
            line.with_user(self.user_cm).write({'awarded_quote_id': quote.id})

    def _approve_all_signatories(self, pr):
        """Approve every pending/waiting approver in sequence until request is approved."""
        approval = pr.approval_request_id.sudo()
        self.assertTrue(approval)
        # Sequential: keep approving the current pending approver.
        for _ in range(len(approval.approver_ids) + 1):
            approval.invalidate_recordset()
            if approval.request_status == 'approved':
                break
            pending = approval.approver_ids.filtered(lambda a: a.status == 'pending')
            self.assertTrue(pending, 'Expected a pending approver')
            pending[0].with_user(pending[0].user_id).action_approve()
        pr.invalidate_recordset()
        self.assertEqual(approval.request_status, 'approved')
        self.assertEqual(pr.state, 'po_ready')
        return approval
