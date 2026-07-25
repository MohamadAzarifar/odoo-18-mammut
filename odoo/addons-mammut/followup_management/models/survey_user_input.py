# -*- coding: utf-8 -*-

from odoo import fields, models


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    followup_id = fields.Many2one(
        'followup.record',
        string='Follow Up',
        index=True,
        ondelete='set null',
    )
