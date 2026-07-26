# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# States reachable via Phase 1 actions. Later phases unlock the rest.
_INTAKE_EDITABLE_STATES = ('draft', 'correction')
_CM_INTAKE_STATES = ('submitted', 'cm_review')
_PHASE1_ALLOWED_TRANSITIONS = {
    'draft': {'submitted'},
    'correction': {'submitted'},
    'submitted': {'rejected', 'correction'},
    'cm_review': {'rejected', 'correction'},
}


class ZvyPurchaseRequest(models.Model):
    _name = 'zvy.purchase.request'
    _description = 'Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    requester_id = fields.Many2one(
        'res.users',
        string='Requester',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )
    description = fields.Text(tracking=True)
    line_ids = fields.One2many(
        'zvy.purchase.request.line',
        'request_id',
        string='Lines',
        copy=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('cm_review', 'CM Review'),
            ('inquiry', 'Inquiry'),
            ('quote_review', 'Quote Review'),
            ('commission', 'Commission'),
            ('signatory', 'Signatory'),
            ('po_ready', 'PO Ready'),
            ('done', 'Done'),
            ('correction', 'Correction'),
            ('rejected', 'Rejected'),
        ],
        default='draft',
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )
    amount_total = fields.Monetary(
        string='Total Estimate',
        currency_field='currency_id',
        compute='_compute_amount_total',
        store=True,
    )
    is_high_value = fields.Boolean(
        string='High Value',
        compute='_compute_routing_flags',
        store=True,
    )
    is_commission_item = fields.Boolean(
        string='Commission Item',
        compute='_compute_routing_flags',
        store=True,
    )
    has_sole_source = fields.Boolean(
        string='Has Sole Source',
        compute='_compute_routing_flags',
        store=True,
    )
    reject_reason = fields.Text(copy=False)
    return_reason = fields.Text(copy=False)

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for request in self:
            request.amount_total = sum(request.line_ids.mapped('price_subtotal'))

    @api.depends(
        'amount_total',
        'company_id.zvy_high_value_threshold',
        'line_ids.is_commission_item',
        'line_ids.sole_source',
    )
    def _compute_routing_flags(self):
        for request in self:
            threshold = request.company_id.zvy_high_value_threshold or 0.0
            request.is_high_value = bool(threshold and request.amount_total >= threshold)
            request.is_commission_item = any(request.line_ids.mapped('is_commission_item'))
            request.has_sole_source = any(request.line_ids.mapped('sole_source'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) in (False, _('New'), 'New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'zvy.purchase.request'
                ) or _('New')
            if vals.get('company_id') and not vals.get('currency_id'):
                company = self.env['res.company'].browse(vals['company_id'])
                vals['currency_id'] = company.currency_id.id
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals:
            new_state = vals['state']
            for request in self:
                if new_state != request.state:
                    allowed = _PHASE1_ALLOWED_TRANSITIONS.get(request.state, set())
                    if new_state not in allowed:
                        raise UserError(_(
                            'Transition from %(current)s to %(target)s is not allowed.',
                            current=request.state,
                            target=new_state,
                        ))
        # Content edits only in draft/correction; CM may still write state/reasons.
        content_keys = set(vals) - {
            'state',
            'reject_reason',
            'return_reason',
            'message_main_attachment_id',
        }
        if content_keys and not self.env.su:
            locked = self.filtered(lambda r: r.state not in _INTAKE_EDITABLE_STATES)
            if locked:
                raise UserError(_(
                    'Purchase request %(name)s can only be edited in Draft or Correction.',
                    name=locked[0].name,
                ))
        return super().write(vals)

    def unlink(self):
        for request in self:
            if request.state != 'draft':
                raise UserError(_(
                    'Only draft purchase requests can be deleted.'
                ))
        return super().unlink()

    def action_submit(self):
        for request in self:
            if request.state not in _INTAKE_EDITABLE_STATES:
                raise UserError(_(
                    'Only draft or correction requests can be submitted.'
                ))
            if not request.line_ids:
                raise ValidationError(_(
                    'Add at least one line before submitting the purchase request.'
                ))
            request.write({'state': 'submitted'})
            request.message_post(body=_('Purchase request submitted for CM review.'))
        return True

    def action_reject(self):
        self.ensure_one()
        if self.state not in _CM_INTAKE_STATES:
            raise UserError(_(
                'Only submitted or CM-review requests can be rejected.'
            ))
        return {
            'name': _('Reject Purchase Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_return_correction(self):
        self.ensure_one()
        if self.state not in _CM_INTAKE_STATES:
            raise UserError(_(
                'Only submitted or CM-review requests can be returned for correction.'
            ))
        return {
            'name': _('Return for Correction'),
            'type': 'ir.actions.act_window',
            'res_model': 'zvy.request.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def _action_reject(self, reason):
        self.ensure_one()
        if not reason or not reason.strip():
            raise ValidationError(_('A reject reason is required.'))
        if self.state not in _CM_INTAKE_STATES:
            raise UserError(_(
                'Only submitted or CM-review requests can be rejected.'
            ))
        self.write({
            'state': 'rejected',
            'reject_reason': reason.strip(),
        })
        self.message_post(body=_('Rejected: %s') % reason.strip())
        self._notify_planner('reject', reason.strip())

    def _action_return_correction(self, reason):
        self.ensure_one()
        if not reason or not reason.strip():
            raise ValidationError(_('A return reason is required.'))
        if self.state not in _CM_INTAKE_STATES:
            raise UserError(_(
                'Only submitted or CM-review requests can be returned for correction.'
            ))
        self.write({
            'state': 'correction',
            'return_reason': reason.strip(),
        })
        self.message_post(body=_('Returned for correction: %s') % reason.strip())
        self._notify_planner('return', reason.strip())

    def _notify_planner(self, event, reason):
        """Post chatter already done by caller; schedule activity for the planner."""
        self.ensure_one()
        if not self.requester_id:
            return
        if event == 'reject':
            summary = _('Purchase request %s rejected') % self.name
            note = _('Your purchase request %s was rejected.\nReason: %s') % (
                self.name, reason,
            )
        else:
            summary = _('Purchase request %s returned for correction') % self.name
            note = _(
                'Your purchase request %s was returned for correction.\nReason: %s'
            ) % (self.name, reason)
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.requester_id.id,
            summary=summary,
            note=note,
        )
