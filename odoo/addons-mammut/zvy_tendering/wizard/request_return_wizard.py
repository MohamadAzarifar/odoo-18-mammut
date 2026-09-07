# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ZvyRequestReturnWizard(models.TransientModel):
    _name = 'zvy.request.return.wizard'
    _description = 'Return Purchase Request for Correction'

    request_id = fields.Many2one(
        'zvy.purchase.request',
        string='Purchase Request',
        required=True,
        ondelete='cascade',
    )
    reason = fields.Text(string='Return Reason', required=True)
    show_destination = fields.Boolean(compute='_compute_show_destination')
    destination = fields.Selection(
        selection=[
            ('planner', 'Planner'),
            ('expert', 'Commercial Expert'),
        ],
        string='Return To',
        default='planner',
    )
    reassign_experts = fields.Boolean(
        string='Re-assign Experts',
        help='Leave off to keep the current line assignments.',
    )
    line_ids = fields.One2many(
        'zvy.request.return.wizard.line',
        'wizard_id',
        string='Lines',
    )

    @api.depends('request_id', 'request_id.state')
    def _compute_show_destination(self):
        for wizard in self:
            wizard.show_destination = wizard.request_id.state == 'cm_review'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        request_id = res.get('request_id') or self.env.context.get(
            'default_request_id'
        )
        if request_id and 'line_ids' in fields_list:
            request = self.env['zvy.purchase.request'].browse(request_id)
            res['line_ids'] = [
                (0, 0, {
                    'line_id': line.id,
                    'expert_user_ids': [(6, 0, line.expert_user_ids.ids)],
                })
                for line in request.line_ids
            ]
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('A return reason is required.'))
        destination = 'planner'
        if self.request_id.state == 'cm_review':
            destination = self.destination or 'planner'
            if destination not in ('planner', 'expert'):
                raise ValidationError(_(
                    'Choose whether to return to the planner or a commercial expert.'
                ))
        if destination == 'expert':
            assignments = None
            if self.reassign_experts:
                if not self.line_ids:
                    raise ValidationError(_('No lines to assign.'))
                assignments = {}
                for wizard_line in self.line_ids:
                    if not wizard_line.expert_user_ids:
                        raise ValidationError(_(
                            'Assign at least one Commercial Expert to every line.'
                        ))
                    assignments[wizard_line.line_id.id] = (
                        wizard_line.expert_user_ids.ids
                    )
            self.request_id._action_return_to_expert(
                self.reason, line_assignments=assignments,
            )
        else:
            self.request_id._action_return_correction(self.reason)
        return {'type': 'ir.actions.act_window_close'}


class ZvyRequestReturnWizardLine(models.TransientModel):
    _name = 'zvy.request.return.wizard.line'
    _description = 'Return for Correction Wizard Line'

    wizard_id = fields.Many2one(
        'zvy.request.return.wizard',
        required=True,
        ondelete='cascade',
    )
    line_id = fields.Many2one(
        'zvy.purchase.request.line',
        string='Request Line',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        related='line_id.product_id',
        string='Product',
    )
    expert_user_ids = fields.Many2many(
        'res.users',
        'zvy_return_wizard_line_expert_rel',
        'wizard_line_id',
        'user_id',
        string='Commercial Experts',
        domain=lambda self: [
            ('groups_id', 'in', [
                self.env.ref('zvy_tendering.group_zvy_commercial_expert').id,
            ]),
        ],
    )
