# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.http import request

import jdatetime
import datetime
from odoo.addons.base_import.models.base_import import ImportValidationError

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _normalize_num_sep(s: str) -> str:
    # ارقام فارسی → لاتین و تبدیل جداکنندهٔ / به -
    return s.translate(PERSIAN_DIGITS).replace("/", "-").strip()

class Import(models.TransientModel):
    _inherit = 'base_import.import'
    _description = 'Base Import'

    # def _parse_date_from_data(self, data, index, name, field_type, options):
    #     dt = datetime.datetime
    #     # Formatterهای استاندارد اودو (TZ-safe)
    #     fmt = fields.Date.to_string if field_type == 'date' else fields.Datetime.to_string
    #
    #     # فرمت‌های ورودی (اولویت با options)
    #     d_fmt = options.get('date_format') or DEFAULT_SERVER_DATE_FORMAT
    #     dt_fmt = options.get('datetime_format') or DEFAULT_SERVER_DATETIME_FORMAT
    #
    #     user = self.env.user  # نه request.env.user
    #
    #     for num, line in enumerate(data):
    #         if not line[index]:
    #             continue
    #
    #         raw = line[index]
    #         v = _normalize_num_sep(raw)
    #
    #         try:
    #             if getattr(user, "calendar_type", "") == "jalaali":
    #                 # --- حالت جلالی ---
    #                 if field_type == 'datetime':
    #                     # ورودی جلالی با فرمت dt_fmt → جلالی datetime
    #                     try:
    #                         jdt = jdatetime.datetime.strptime(v, dt_fmt)
    #                     except ValueError:
    #                         # اگر کاربر تاریخ-زمان را با فرمت تاریخ ساده وارد کرده بود
    #                         # (مثلاً فقط YYYY-MM-DD جلالی)، یک بار با d_fmt امتحان کن
    #                         jdt = jdatetime.datetime.combine(
    #                             jdatetime.date.strptime(v, d_fmt), jdatetime.time(0, 0, 0)
    #                         )
    #                     gdt = jdt.togregorian()  # datetime میلادی (naive)
    #                     # بده به formatter اودو تا TZ/UTC را هندل کند
    #                     line[index] = fmt(gdt)
    #                 else:
    #                     # field_type == 'date'
    #                     try:
    #                         jdate = jdatetime.date.strptime(v, d_fmt)
    #                     except ValueError:
    #                         # اگر کاربر تاریخ را با فرمت datetime وارد کرد (نادر ولی ممکن)
    #                         jdate = jdatetime.datetime.strptime(v, dt_fmt).date()
    #                     gdate = jdate.togregorian()
    #                     line[index] = fmt(gdate)
    #             else:
    #                 # --- حالت میلادی معمولی ---
    #                 if field_type == 'datetime':
    #                     try:
    #                         line[index] = fmt(dt.strptime(v, dt_fmt))
    #                     except ValueError:
    #                         # به‌ندرت: اگر datetime نبود، شاید فقط date داده شده
    #                         line[index] = fmt(dt.strptime(v, d_fmt))
    #                 else:
    #                     line[index] = fmt(dt.strptime(v, d_fmt))
    #
    #         except ValueError as e:
    #             # پیام استاندارد اودو برای ایمپورت
    #             raise ImportValidationError(
    #                 _("Column %(column)s contains incorrect values. Error in line %(line)d: %(error)s",
    #                   column=name, line=num + 1, error=e),
    #                 field=name, field_type=field_type
    #             )
    #         except Exception as e:
    #             raise ImportValidationError(
    #                 _("Error Parsing Date [%(field)s:L%(line)d]: %(error)s",
    #                   field=name, line=num + 1, error=e),
    #                 field=name, field_type=field_type

    #             )

    def _parse_date_from_data(self, data, index, name, field_type, options):
        fmt = fields.Date.to_string if field_type == 'date' else fields.Datetime.to_string

        d_fmt = options.get('date_format') or DEFAULT_SERVER_DATE_FORMAT
        dt_fmt = options.get('datetime_format') or DEFAULT_SERVER_DATETIME_FORMAT

        user = self.env.user

        def _parse_gregorian_date_str(s: str) -> datetime.date:
            return datetime.datetime.strptime(s, d_fmt).date()

        def _parse_gregorian_dt_str(s: str) -> datetime.datetime:
            try:
                return datetime.datetime.strptime(s, dt_fmt)
            except ValueError:
                # اگر فقط date بود
                return datetime.datetime.strptime(s, d_fmt)

        def _parse_jalali_date_str(s: str) -> datetime.date:
            # بدون استفاده از jdatetime.date.strptime
            try:
                jdt = jdatetime.datetime.strptime(s, d_fmt)  # "yyyy-mm-dd" جلالی
            except ValueError:
                jdt = jdatetime.datetime.strptime(s, dt_fmt)  # شاید تاریخ را با datetime داده
            return jdt.togregorian().date()

        def _parse_jalali_dt_str(s: str) -> datetime.datetime:
            # بدون استفاده از jdatetime.date.strptime
            try:
                jdt = jdatetime.datetime.strptime(s, dt_fmt)
            except ValueError:
                # اگر فقط تاریخ بود، ساعت 00:00
                jdt0 = jdatetime.datetime.strptime(s, d_fmt)
                jdt = jdatetime.datetime.combine(jdt0.date(), jdatetime.time(0, 0, 0))
            return jdt.togregorian()

        for num, line in enumerate(data):
            if not line[index]:
                continue

            raw = line[index]

            try:
                # 1) اگر اکسل مقدار را به صورت date/datetime داده باشد
                if isinstance(raw, datetime.datetime):
                    line[index] = fmt(raw if field_type == 'datetime' else raw.date())
                    continue

                if isinstance(raw, datetime.date):
                    if field_type == 'date':
                        line[index] = fmt(raw)
                    else:
                        line[index] = fmt(datetime.datetime.combine(raw, datetime.time(0, 0, 0)))
                    continue

                # 2) رشته‌ای: نرمال‌سازی
                v = _normalize_num_sep(str(raw))

                # 3) تبدیل
                if getattr(user, "calendar_type", "") == "jalaali":
                    if field_type == 'datetime':
                        gdt = _parse_jalali_dt_str(v)
                        line[index] = fmt(gdt)
                    else:
                        gdate = _parse_jalali_date_str(v)
                        line[index] = fmt(gdate)
                else:
                    if field_type == 'datetime':
                        gdt = _parse_gregorian_dt_str(v)
                        line[index] = fmt(gdt)
                    else:
                        gdate = _parse_gregorian_date_str(v)
                        line[index] = fmt(gdate)

            except ValueError as e:
                raise ImportValidationError(
                    _("Column %(column)s contains incorrect values. Error in line %(line)d: %(error)s",
                      column=name, line=num + 1, error=e),
                    field=name, field_type=field_type
                )
            except Exception as e:
                raise ImportValidationError(
                    _("Error Parsing Date [%(field)s:L%(line)d]: %(error)s",
                      field=name, line=num + 1, error=e),
                    field=name, field_type=field_type
                )
