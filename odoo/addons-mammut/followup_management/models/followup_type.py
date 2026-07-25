# -*- coding: utf-8 -*-

from odoo import fields, models


class FollowupType(models.Model):
    _name = 'followup.type'
    _description = 'Follow-up Type'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True, translate=False)
    survey_template_id = fields.Many2one('survey.survey', string='Survey Template')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Follow-up type code must be unique.'),
    ]
