# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ZvyCommissionAssignWizard(models.TransientModel):
    _name = 'zvy.commission.assign.wizard'
    _description = 'Assign Commission Experts'

    case_id = fields.Many2one(
        'zvy.commission.case',
        string='Commission Case',
        required=True,
        ondelete='cascade',
    )
    expert_user_ids = fields.Many2many(
        'res.users',
        'zvy_commission_assign_wizard_expert_rel',
        'wizard_id',
        'user_id',
        string='Commission Experts',
        domain=lambda self: [
            ('groups_id', 'in', [
                self.env.ref('zvy_tendering.group_zvy_commission_expert').id,
            ]),
        ],
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        case_id = res.get('case_id') or self.env.context.get('default_case_id')
        if case_id and 'expert_user_ids' in fields_list:
            case = self.env['zvy.commission.case'].browse(case_id)
            res['expert_user_ids'] = [(6, 0, case.expert_user_ids.ids)]
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.expert_user_ids:
            raise ValidationError(_(
                'Select at least one Commission Expert before assigning.'
            ))
        self.case_id._action_assign_experts(self.expert_user_ids.ids)
        return {'type': 'ir.actions.act_window_close'}
