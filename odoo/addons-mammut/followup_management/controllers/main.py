# -*- coding: utf-8 -*-

from odoo import http
from odoo.addons.survey.controllers.main import Survey
from odoo.http import request


class FollowupSurvey(Survey):
    """Allow internal admins to fill follow-up surveys on behalf of customers."""

    def _check_validity(self, survey_token, answer_token, ensure_token=True, check_partner=True):
        validity_code = super()._check_validity(
            survey_token, answer_token, ensure_token, check_partner,
        )
        if validity_code != 'answer_wrong_user' or not check_partner:
            return validity_code

        _survey_sudo, answer_sudo = self._fetch_from_access_token(survey_token, answer_token)
        if (
            answer_sudo
            and answer_sudo.followup_id
            and not request.env.user._is_public()
            and request.env.user.has_group('base.group_system')
        ):
            return True
        return validity_code

    @http.route()
    def survey_retry(self, survey_token, answer_token, **post):
        survey_sudo, _answer_sudo = self._fetch_from_access_token(survey_token, answer_token)
        if survey_sudo.hide_take_again:
            return request.redirect('/survey/%s/%s' % (survey_token, answer_token))
        return super().survey_retry(survey_token, answer_token, **post)
