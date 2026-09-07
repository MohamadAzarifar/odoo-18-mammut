# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    zvy_purchase_request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        copy=False,
        index=True,
        ondelete='set null',
    )
    zvy_resume_commission = fields.Boolean(
        string='Resume Commission After Sign-off',
        copy=False,
        help='Set when Holding Commission returned the PR to the last signatory. '
             'Completing this chain reopens the commission case (FR-45).',
    )

    def _zvy_is_current_signatory(self, pr):
        """True when this document is the PR's in-progress signatory chain."""
        return bool(pr and pr.approval_request_id and pr.approval_request_id == self)

    def _zvy_live_signatory_pr(self):
        """Current PR when this document is the live signatory chain, else empty."""
        self.ensure_one()
        pr = self.zvy_purchase_request_id.sudo()
        if self._zvy_is_current_signatory(pr) and pr.state == 'signatory':
            return pr
        return pr.browse()

    def action_approve(self, approver=None):
        res = super().action_approve(approver=approver)
        for request in self:
            pr = request.zvy_purchase_request_id.sudo()
            if not request._zvy_is_current_signatory(pr) or pr.state != 'signatory':
                continue
            if request.request_status == 'approved':
                if request.zvy_resume_commission:
                    pr._action_open_commission_case()
                else:
                    pr._action_route_after_signatory()
        return res

    def action_refuse(self, approver=None):
        live = self.filtered(lambda r: r._zvy_live_signatory_pr())
        others = self - live
        res = True
        if live:
            live.ensure_one()
            if not self.env.context.get('zvy_skip_return_wizard'):
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Return Reason'),
                    'res_model': 'zvy.request.signatory.return.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_approval_request_id': live.id,
                    },
                }
            live._zvy_return_to_previous_approver(approver=approver)
        if others:
            res = super(ApprovalRequest, others).action_refuse(approver=approver)
        return res

    def _zvy_resolve_approver(self, approver=None):
        self.ensure_one()
        if isinstance(approver, models.BaseModel) and approver:
            return approver[:1]
        found = self.approver_ids.filtered(
            lambda a: a.user_id == self.env.user
        )[:1]
        if not found:
            raise UserError(_('Only a pending signatory can return this request.'))
        return found

    def _zvy_previous_approver(self, current):
        """Previous signatory in sequence who can receive a bounce (FR-45)."""
        self.ensure_one()
        current = current[:1]
        if not current:
            return self.env['approval.approver']
        earlier = self.approver_ids.filtered(
            lambda a: (
                (a.sequence, a.id) < (current.sequence, current.id)
                and a.status in ('approved', 'waiting', 'new')
            )
        ).sorted(lambda a: (a.sequence, a.id))
        return earlier[-1:] if earlier else self.env['approval.approver']

    def _zvy_return_to_previous_approver(self, approver=None):
        """Bounce to the previous signatory, or refuse to CM if this is the first."""
        self.ensure_one()
        pr = self._zvy_live_signatory_pr()
        if not pr:
            return True
        reason = (self.env.context.get('zvy_refuse_reason') or '').strip()
        if not reason:
            raise ValidationError(_('A return reason is required.'))
        current = self._zvy_resolve_approver(approver=approver).sudo()
        if current.status != 'pending':
            raise UserError(_(
                'Only the pending signatory can return this request.'
            ))
        previous = self.sudo()._zvy_previous_approver(current)
        if previous:
            self.sudo()._get_user_approval_activities(
                user=current.user_id
            ).unlink()
            current.write({'status': 'waiting'})
            previous.write({'status': 'pending'})
            previous._create_activity()
            pr.write({'return_reason': reason})
            body = _(
                'Signatory %(actor)s returned the request to %(dest)s.\n'
                'Reason: %(reason)s'
            ) % {
                'actor': current.user_id.display_name,
                'dest': previous.user_id.display_name,
                'reason': reason,
            }
            pr.message_post(body=body)
            self.sudo().message_post(body=body)
            return True
        res = super().action_refuse(approver=current)
        pr.write({
            'state': 'cm_review',
            'return_reason': reason,
        })
        body = _(
            'Signatory approval refused (%s); returned to Commercial Manager.\n'
            'Reason: %s'
        ) % (self.display_name, reason)
        pr.message_post(body=body)
        return res

    def action_open_zvy_purchase_request(self):
        self.ensure_one()
        if not self.zvy_purchase_request_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'zvy.purchase.request',
            'res_id': self.zvy_purchase_request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ApprovalApprover(models.Model):
    _inherit = 'approval.approver'

    def action_refuse(self):
        """Return the request-level result so the FR-45 reason wizard opens."""
        return self.request_id.action_refuse(self)
