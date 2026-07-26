# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class ZvyCommissionReview(models.Model):
    _name = 'zvy.commission.review'
    _description = 'Commission Expert Review'
    _order = 'id'

    case_id = fields.Many2one(
        'zvy.commission.case',
        string='Case',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='case_id.company_id',
        store=True,
        index=True,
    )
    expert_user_id = fields.Many2one(
        'res.users',
        string='Commission Expert',
        required=True,
        ondelete='restrict',
        index=True,
    )
    recommendation = fields.Selection(
        selection=[
            ('approve', 'Approve'),
            ('reject', 'Reject'),
            ('request_corrections', 'Request Corrections'),
        ],
        string='Recommendation',
    )
    notes_accuracy = fields.Text(string='Accuracy Notes')
    notes_policy = fields.Text(string='Policy Notes')
    notes_suppliers = fields.Text(string='Suppliers Notes')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
        ],
        default='draft',
        required=True,
        copy=False,
        index=True,
    )

    def write(self, vals):
        if not self.env.su:
            for review in self:
                if review.state != 'draft':
                    raise UserError(_(
                        'Submitted reviews cannot be edited.'
                    ))
                is_admin = self.env.user.has_group(
                    'zvy_tendering.group_zvy_tendering_admin'
                )
                is_mgr = self.env.user.has_group(
                    'zvy_tendering.group_zvy_commission_manager'
                )
                if (
                    review.expert_user_id != self.env.user
                    and not (is_admin or is_mgr)
                ):
                    raise UserError(_(
                        'You can only edit your own commission review.'
                    ))
        return super().write(vals)

    def action_submit(self):
        for review in self:
            if review.state != 'draft':
                raise UserError(_('Only draft reviews can be submitted.'))
            if not self.env.su and review.expert_user_id != self.env.user:
                is_admin = self.env.user.has_group(
                    'zvy_tendering.group_zvy_tendering_admin'
                )
                if not is_admin:
                    raise UserError(_(
                        'Only the assigned expert can submit this review.'
                    ))
            if not review.recommendation:
                raise ValidationError(_(
                    'Select a recommendation before submitting the review.'
                ))
            review.write({'state': 'submitted'})
            review.case_id.message_post(body=_(
                'Review submitted by %(expert)s: %(rec)s'
            ) % {
                'expert': review.expert_user_id.display_name,
                'rec': review.recommendation,
            })
        return True
