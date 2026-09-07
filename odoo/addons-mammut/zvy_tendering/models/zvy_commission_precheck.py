# -*- coding: utf-8 -*-
from odoo import fields, models


class ZvyCommissionPrecheck(models.Model):
    _name = 'zvy.commission.precheck'
    _description = 'Commission Validation Report Line'
    _order = 'sequence, id'

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
    sequence = fields.Integer(string='Check', required=True, index=True)
    name = fields.Char(string='Name', required=True)
    result = fields.Selection(
        selection=[
            ('pass', 'Pass'),
            ('fail', 'Fail'),
            ('skipped', 'Skipped'),
        ],
        string='Result',
        required=True,
        index=True,
    )
    message = fields.Text(string='Details')
