# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.addons.web.controllers.export import CSVExport, ExcelExport
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.http import request
from odoo.tools import pycompat

import io
import datetime
import jdatetime


class CSVExportInherit(CSVExport):

    def from_data(self, fields, columns_headers, rows):
        if request.env.user.calendar_type == 'jalaali':
            fp = io.BytesIO()
            writer = pycompat.csv_writer(fp, quoting=1)
            writer.writerow(fields)
            for data in rows:
                row = []
                for d in data:
                    # Spreadsheet apps tend to detect formulas on leading =, + and -
                    if isinstance(d, str) and d.startswith(('=', '-', '+')):
                        d = "'" + d
                    ########## Overrided ##########
                    elif isinstance(d, datetime.datetime):
                        d = jdatetime.datetime.fromgregorian(datetime=d).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                    elif isinstance(d, datetime.date):
                        d = jdatetime.datetime.fromgregorian(date=d).strftime(DEFAULT_SERVER_DATE_FORMAT)
                    ########## ######### ##########
                    row.append(pycompat.to_text(d))
                writer.writerow(row)

            return fp.getvalue()
        else:
            return super().from_data(fields, columns_headers, rows)


class ExcelExportInherit(ExcelExport):

    def from_group_data(self, fields, columns_headers, groups):
        if request.env.user.calendar_type == 'jalaali':
            for group_name, group in groups.children.items():
                if group.children:
                    self.from_group_data(fields, columns_headers, groups)

                for data in group.data:
                    for i in range(len(data)):
                        if isinstance(data[i], datetime.datetime):
                            data[i] = jdatetime.datetime.fromgregorian(datetime=data[i]).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                        elif isinstance(data[i], datetime.date):
                            data[i] = jdatetime.datetime.fromgregorian(date=data[i]).strftime(DEFAULT_SERVER_DATE_FORMAT)

        return super().from_group_data(fields, columns_headers, groups)


    def from_data(self, fields, columns_headers, rows):
        if request.env.user.calendar_type == 'jalaali':
            for data in rows:
                for i in range(len(data)):
                    if isinstance(data[i], datetime.datetime):
                        data[i] = jdatetime.datetime.fromgregorian(datetime=data[i]).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                    elif isinstance(data[i], datetime.date):
                        data[i] = jdatetime.datetime.fromgregorian(date=data[i]).strftime(DEFAULT_SERVER_DATE_FORMAT)
        return super().from_data(fields, columns_headers, rows)