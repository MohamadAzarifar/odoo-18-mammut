# -*- encoding: utf-8 -*-
import odoo.tools.date_utils as odoo_date_utils

from dateutil.relativedelta import relativedelta
import jdatetime

from .globals import jdate_utils

odoo_get_timedelta = odoo_date_utils.get_timedelta
def artarad_web_persian_calendar_get_timedelta(qty, granularity):
    if granularity == 'jmonth':
        return relativedelta(days=int(qty*30.5))
    elif granularity == 'jyear':
        return relativedelta(days=qty*365)
    else:
        return odoo_get_timedelta(qty, granularity)
odoo_date_utils.get_timedelta = artarad_web_persian_calendar_get_timedelta

odoo_start_of = odoo_date_utils.start_of
def artarad_web_persian_calendar_start_of(value, granularity):
    jvalue = jdatetime.date.fromgregorian(date=value)
    if granularity == 'jmonth':
        return jdate_utils.get_month(jvalue)[0].togregorian()
    elif granularity == 'jquarter':
        return jdate_utils.get_quarter(jvalue)[0].togregorian()
    elif granularity == 'jyear':
        return jdate_utils.get_year(jvalue)[0].togregorian()
    else:
        return odoo_start_of(value, granularity)
odoo_date_utils.start_of = artarad_web_persian_calendar_start_of

odoo_end_of = odoo_date_utils.end_of
def artarad_web_persian_calendar_end_of(value, granularity):
    jvalue = jdatetime.date.fromgregorian(date=value)
    if granularity == 'jmonth':
        return jdate_utils.get_month(jvalue)[1].togregorian()
    elif granularity == 'jquarter':
        return jdate_utils.get_quarter(jvalue)[1].togregorian()
    elif granularity == 'jyear':
        return jdate_utils.get_year(jvalue)[1].togregorian()
    else:
        return odoo_end_of(value, granularity)
odoo_date_utils.end_of = artarad_web_persian_calendar_end_of