from odoo import models, fields, api, exceptions, _
from odoo.http import request

class artaradHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        session_info = super(artaradHttp, self).session_info()
        session_info['user_calendar_type'] = request.session.uid and self.env.user.calendar_type or 'jalaali'
        return session_info

    @api.model
    def get_frontend_session_info(self):
        session_info = super(artaradHttp, self).get_frontend_session_info()
        session_info['user_calendar_type'] = request.session.uid and self.env.user.calendar_type or 'jalaali'
        return session_info