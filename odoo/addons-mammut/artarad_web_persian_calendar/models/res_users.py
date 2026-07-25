from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

import datetime
import jdatetime
import num2fawords
from ..globals import jdate_utils

class artaradResUser(models.Model):
    _inherit = "res.users"

    calendar_type = fields.Selection([('jalaali','Jalaali'), ('gregorian','Gregorian')], default='jalaali', required=True)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['calendar_type']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['calendar_type']


    def get_jalali_date(self, g_date):
        if isinstance(g_date, str):
            g_date_obj = datetime.datetime.strptime(g_date, DEFAULT_SERVER_DATE_FORMAT)
        else:
            g_date_obj = g_date

        j_date_obj = jdatetime.date.fromgregorian(date=g_date_obj)
        j_date = jdatetime.date.strftime(j_date_obj,'%Y/%m/%d')

        return j_date

    def get_jalali_datetime(self, g_datetime):
        if isinstance(g_datetime, str):
            g_datetime_obj = datetime.datetime.strptime(g_datetime, DEFAULT_SERVER_DATETIME_FORMAT)
        else:
            g_datetime_obj = g_datetime

        j_datetime_obj = jdatetime.datetime.fromgregorian(date=g_datetime_obj)
        j_datetime = jdatetime.datetime.strftime(j_datetime_obj, '%Y/%m/%d')

        return j_datetime

    def get_farsi_words(self, number):
        return num2fawords.words(number)

    def get_jalali_format(self,g_date):
        jdate = jdatetime.date.fromgregorian(date=g_date)
        name = str(jdate.year) + ' ' + jdate_utils.get_month_name(jdate, 'fa_IR')
        return name

    def get_jalali_day(self,g_date):
        jdate = jdatetime.date.fromgregorian(date=g_date)
        name = str(jdate.day)
        return name

    def get_week_name(self,g_date):
        jdate = jdatetime.date.fromgregorian(date=g_date)
        return jdate_utils.get_weekday_name(jdate, 'fa_IR')