# -*- coding: utf-8 -*-

from odoo import fields, models


class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    hide_take_again = fields.Boolean(
        string='Hide Take Again Button',
        help='If enabled, the "Take Again" / "Retry" button is hidden on the survey completion page.',
    )
