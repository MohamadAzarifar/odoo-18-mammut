# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import date_utils
from odoo.tools.misc import get_lang
import odoo
import odoo.models as MODELS

import logging
_logger = logging.getLogger(__name__)

import datetime
import jdatetime
import dateutil
import pytz
import collections
import re

from ..globals import jdate_utils


class artaradBase(models.AbstractModel):
    _inherit = 'base'


    def _read_group_groupby(self, groupby_spec: str, query: MODELS.Query) -> MODELS.SQL:
        """ Return a pair (<SQL expression>, [<field names used in SQL expression>])
        corresponding to the given groupby element.
        """
        if self.env.user.calendar_type == 'jalaali':
            fname, property_name, granularity = MODELS.parse_read_group_spec(groupby_spec)
            if fname not in self:
                raise ValueError(f"Invalid field {fname!r} on model {self._name!r}")

            field = self._fields[fname]

            if field.type == 'properties':
                sql_expr = self._read_group_groupby_properties(fname, property_name, query)

            elif property_name:
                raise ValueError(f"Property access on non-property field: {groupby_spec!r}")

            elif granularity and field.type not in ('datetime', 'date', 'properties'):
                raise ValueError(f"Granularity set on a no-datetime field or property: {groupby_spec!r}")

            elif field.type == 'many2many':
                alias = self._table
                if field.related and not field.store:
                    __, field, alias = self._traverse_related_sql(alias, field, query)

                if not field.store:
                    raise ValueError(f"Group by non-stored many2many field: {groupby_spec!r}")
                # special case for many2many fields: prepare a query on the comodel
                # in order to reuse the mechanism _apply_ir_rules, then inject the
                # query as an extra condition of the left join
                comodel = self.env[field.comodel_name]
                coquery = comodel._where_calc([], active_test=False)
                comodel._apply_ir_rules(coquery)
                # LEFT JOIN {field.relation} AS rel_alias ON
                #     alias.id = rel_alias.{field.column1}
                #     AND rel_alias.{field.column2} IN ({coquery})
                rel_alias = query.make_alias(alias, field.name)
                condition = MODELS.SQL(
                    "%s = %s",
                    MODELS.SQL.identifier(alias, 'id'),
                    MODELS.SQL.identifier(rel_alias, field.column1),
                )
                if coquery.where_clause:
                    condition = MODELS.SQL(
                        "%s AND %s IN %s",
                        condition,
                        MODELS.SQL.identifier(rel_alias, field.column2),
                        coquery.subselect(),
                    )
                query.add_join("LEFT JOIN", rel_alias, field.relation, condition)
                return MODELS.SQL.identifier(rel_alias, field.column2)

            else:
                sql_expr = self._field_to_sql(self._table, fname, query)

            if field.type == 'datetime' and (tz := self.env.context.get('tz')):
                if tz in pytz.all_timezones_set:
                    sql_expr = MODELS.SQL("timezone(%s, timezone('UTC', %s))", self.env.context['tz'], sql_expr)
                else:
                    _logger.warning("Grouping in unknown / legacy timezone %r", tz)

            if field.type in ('datetime', 'date') or (field.type == 'properties' and granularity):
                if not granularity:
                    raise ValueError(f"Granularity not set on a date(time) field: {groupby_spec!r}")
                if granularity not in MODELS.READ_GROUP_ALL_TIME_GRANULARITY:
                    raise ValueError(f"Granularity specification isn't correct: {granularity!r}")

                ########## overrided ##########
                if field.type == 'datetime':
                    tail = " 00:00:00"
                else:
                    tail = ""

                if granularity=='day':
                    sql_expr = MODELS.SQL("g2j(%s) || %s", sql_expr, tail)
                elif granularity == 'week':
                    first_week_day = int(get_lang(self.env).week_start) - 1
                    days_offset = first_week_day and 7 - first_week_day
                    interval = f'-{days_offset} DAY'
                    sql_expr = MODELS.SQL("g2j((date_trunc('week', %s::timestamp - INTERVAL %s) + INTERVAL %s)) || %s", sql_expr, interval, interval, tail)
                elif granularity == 'month':
                    sql_expr = MODELS.SQL("substring(g2j(%s), 0, 8) || '-01' || %s", sql_expr, tail)
                elif granularity == 'quarter':
                    sql_expr = MODELS.SQL("""case
                                            when substring(g2j(%s), 6, 2) < '04' then substring(g2j(%s), 0, 5) || '-01-01' || %s
                                            when substring(g2j(%s), 6, 2) < '07' then substring(g2j(%s), 0, 5) || '-04-01' || %s
                                            when substring(g2j(%s), 6, 2) < '10' then substring(g2j(%s), 0, 5) || '-07-01' || %s
                                            when substring(g2j(%s), 6, 2) < '13' then substring(g2j(%s), 0, 5) || '-10-01' || %s
                                        end""", *(sql_expr, sql_expr, tail) * 4)
                elif granularity == 'year':
                    sql_expr =  MODELS.SQL("substring(g2j(%s), 0, 5) || '-01-01' || %s", sql_expr, tail)
                ########## ######### ##########

            elif field.type == 'boolean':
                sql_expr = MODELS.SQL("COALESCE(%s, FALSE)", sql_expr)

            return sql_expr
        else:
            return super()._read_group_groupby(groupby_spec, query)


    def _read_group_postprocess_groupby(self, groupby_spec, raw_values):
        """ Convert the given values of ``groupby_spec``
        from PostgreSQL to the format returned by method ``_read_group()``.

        The formatting rules can be summarized as:
        - groupby values of relational fields are converted to recordsets with a correct prefetch set;
        - NULL values are converted to empty values corresponding to the given aggregate.
        """
        if self.env.user.calendar_type == 'jalaali':
            # check if groupby is on a date or datetime field
            if re.search("\w+\:(day|week|month|quarter|year)", groupby_spec):
                raw_values = list(raw_values)
                for i in range(len(raw_values)):
                    if raw_values[i]:
                        try:
                            raw_values[i] = jdatetime.datetime.strptime(raw_values[i], DEFAULT_SERVER_DATETIME_FORMAT).togregorian()
                        except:
                            raw_values[i] = jdatetime.datetime.strptime(raw_values[i], DEFAULT_SERVER_DATE_FORMAT).date().togregorian()
                raw_values = tuple(raw_values)

        return super()._read_group_postprocess_groupby(groupby_spec, raw_values)


    @api.model
    def _read_group_fill_temporal(self, data, groupby, annoted_aggregates,
                                  fill_from=False, fill_to=False, min_groups=False):
        """Helper method for filling date/datetime 'holes' in a result set.

        We are in a use case where data are grouped by a date field (typically
        months but it could be any other interval) and displayed in a chart.

        Assume we group records by month, and we only have data for June,
        September and December. By default, plotting the result gives something
        like::

                                                ___
                                      ___      |   |
                                     |   | ___ |   |
                                     |___||___||___|
                                      Jun  Sep  Dec

        The problem is that December data immediately follow September data,
        which is misleading for the user. Adding explicit zeroes for missing
        data gives something like::

                                                           ___
                             ___                          |   |
                            |   |           ___           |   |
                            |___| ___  ___ |___| ___  ___ |___|
                             Jun  Jul  Aug  Sep  Oct  Nov  Dec

        To customize this output, the context key "fill_temporal" can be used
        under its dictionary format, which has 3 attributes : fill_from,
        fill_to, min_groups (see params of this function)

        Fill between bounds:
        Using either `fill_from` and/or `fill_to` attributes, we can further
        specify that at least a certain date range should be returned as
        contiguous groups. Any group outside those bounds will not be removed,
        but the filling will only occur between the specified bounds. When not
        specified, existing groups will be used as bounds, if applicable.
        By specifying such bounds, we can get empty groups before/after any
        group with data.

        If we want to fill groups only between August (fill_from)
        and October (fill_to)::

                                                     ___
                                 ___                |   |
                                |   |      ___      |   |
                                |___| ___ |___| ___ |___|
                                 Jun  Aug  Sep  Oct  Dec

        We still get June and December. To filter them out, we should match
        `fill_from` and `fill_to` with the domain e.g. ``['&',
        ('date_field', '>=', 'YYYY-08-01'), ('date_field', '<', 'YYYY-11-01')]``::

                                         ___
                                    ___ |___| ___
                                    Aug  Sep  Oct

        Minimal filling amount:
        Using `min_groups`, we can specify that we want at least that amount of
        contiguous groups. This amount is guaranteed to be provided from
        `fill_from` if specified, or from the lowest existing group otherwise.
        This amount is not restricted by `fill_to`. If there is an existing
        group before `fill_from`, `fill_from` is still used as the starting
        group for min_groups, because the filling does not apply on that
        existing group. If neither `fill_from` nor `fill_to` is specified, and
        there is no existing group, no group will be returned.

        If we set min_groups = 4::

                                         ___
                                    ___ |___| ___ ___
                                    Aug  Sep  Oct Nov

        :param list data: the data containing groups
        :param list groupby: name of the first group by
        :param list aggregated_fields: list of aggregated fields in the query
        :param str fill_from: (inclusive) string representation of a
            date/datetime, start bound of the fill_temporal range
            formats: date -> %Y-%m-%d, datetime -> %Y-%m-%d %H:%M:%S
        :param str fill_to: (inclusive) string representation of a
            date/datetime, end bound of the fill_temporal range
            formats: date -> %Y-%m-%d, datetime -> %Y-%m-%d %H:%M:%S
        :param int min_groups: minimal amount of required groups for the
            fill_temporal range (should be >= 1)
        :rtype: list
        :return: list
        """
        if self.env.user.calendar_type == 'jalaali':
            # TODO: remove min_groups
            first_group = groupby[0]
            field_name = first_group.split(':')[0].split(".")[0]
            field = self._fields[field_name]
            if field.type not in ('date', 'datetime') and not (field.type == 'properties' and ':' in first_group):
                return data

            granularity = first_group.split(':')[1] if ':' in first_group else 'month'
            days_offset = 0
            if granularity == 'week':
                # _read_group_process_groupby week groups are dependent on the
                # locale, so filled groups should be too to avoid overlaps.
                first_week_day = int(get_lang(self.env).week_start) - 1
                days_offset = first_week_day and 7 - first_week_day
            interval = MODELS.READ_GROUP_TIME_GRANULARITY[granularity]
            tz = False
            if field.type == 'datetime' and self._context.get('tz') in pytz.all_timezones_set:
                tz = pytz.timezone(self._context['tz'])

            # TODO: refactor remaing lines here

            # existing non null datetimes
            existing = [d[first_group] for d in data if d[first_group]] or [None]
            # assumption: existing data is sorted by field 'groupby_name'
            existing_from, existing_to = existing[0], existing[-1]
            if fill_from:
                fill_from = odoo.fields.Datetime.to_datetime(fill_from) if isinstance(fill_from, datetime.datetime) else odoo.fields.Date.to_date(fill_from)
                fill_from = date_utils.start_of(fill_from, granularity) - datetime.timedelta(days=days_offset)
                if tz:
                    fill_from = tz.localize(fill_from)
            elif existing_from:
                fill_from = existing_from
            if fill_to:
                fill_to = odoo.fields.Datetime.to_datetime(fill_to) if isinstance(fill_to, datetime.datetime) else odoo.fields.Date.to_date(fill_to)
                fill_to = date_utils.start_of(fill_to, granularity) - datetime.timedelta(days=days_offset)
                if tz:
                    fill_to = tz.localize(fill_to)
            elif existing_to:
                fill_to = existing_to

            if not fill_to and fill_from:
                fill_to = fill_from
            if not fill_from and fill_to:
                fill_from = fill_to
            if not fill_from and not fill_to:
                return data

            if min_groups > 0:
                fill_to = max(fill_to, fill_from + (min_groups - 1) * interval)

            if fill_to < fill_from:
                return data

            ########## overrided #########
            if isinstance(fill_from, datetime.datetime):
                j_fill_from = jdatetime.datetime.fromgregorian(datetime=fill_from)
                j_fill_to = jdatetime.datetime.fromgregorian(datetime=fill_to)
            else:
                j_fill_from = jdatetime.datetime.fromgregorian(date=fill_from).date()
                j_fill_to = jdatetime.datetime.fromgregorian(date=fill_to).date()

            j_required_dates = jdate_utils.get_date_range(j_fill_from, j_fill_to, interval)
            required_dates = [dt.togregorian() for dt in j_required_dates]
            ########## ######### ##########

            if existing[0] is None:
                existing = list(required_dates)
            else:
                existing = sorted(set().union(existing, required_dates))

            empty_item = {
                name: self._read_group_empty_value(spec)
                for name, spec in annoted_aggregates.items()
            }
            for group in groupby[1:]:
                empty_item[group] = self._read_group_empty_value(group)

            grouped_data = collections.defaultdict(list)
            for d in data:
                grouped_data[d[first_group]].append(d)

            result = []
            for dt in existing:
                result.extend(grouped_data[dt] or [dict(empty_item, **{first_group: dt})])

            if False in grouped_data:
                result.extend(grouped_data[False])

            return result
        else:
            return super()._read_group_fill_temporal(data, groupby, annoted_aggregates, fill_from, fill_to, min_groups)


    @api.model
    def _read_group_format_result(self, rows_dict, lazy_groupby):
        """
            Helper method to format the data contained in the dictionary data by
            adding the domain corresponding to its values, the groupbys in the
            context and by properly formatting the date/datetime values.

        :param data: a single group
        :param annotated_groupbys: expanded grouping metainformation
        :param groupby: original grouping metainformation
        """
        if self.env.user.calendar_type == 'jalaali':
            for group in lazy_groupby:
                field_name = group.split(':')[0].split('.')[0]
                field = self._fields[field_name]

                if field.type in ('date', 'datetime'):
                    locale = get_lang(self.env).code
                    fmt = DEFAULT_SERVER_DATETIME_FORMAT if field.type == 'datetime' else DEFAULT_SERVER_DATE_FORMAT
                    granularity = group.split(':')[1] if ':' in group else 'month'
                    interval = MODELS.READ_GROUP_TIME_GRANULARITY[granularity]

                elif field.type == "properties":
                    self._read_group_format_result_properties(rows_dict, group)
                    continue

                for row in rows_dict:
                    value = row[group]

                    if field.type in ('many2one', 'many2many') and isinstance(value, MODELS.BaseModel):
                        row[group] = (value.id, value.sudo().display_name) if value else False
                        value = value.id

                    additional_domain = [(field_name, '=', value)]

                    if field.type in ('date', 'datetime'):
                        ########## overrided ##########
                        if value:
                            if isinstance(value, datetime.datetime):
                                j_range_start = jdatetime.datetime.fromgregorian(datetime=value)
                            else:
                                j_range_start = jdatetime.datetime.fromgregorian(date=value).date()

                            if interval == dateutil.relativedelta.relativedelta(days=1):
                                j_range_start, j_range_end = jdate_utils.get_day(j_range_start) 
                            elif interval == datetime.timedelta(7):
                                j_range_start, j_range_end = jdate_utils.get_week(j_range_start)                              
                            elif interval == dateutil.relativedelta.relativedelta(months=1):
                                j_range_start, j_range_end = jdate_utils.get_month(j_range_start)
                            elif interval == dateutil.relativedelta.relativedelta(months=3):
                                j_range_start, j_range_end = jdate_utils.get_quarter(j_range_start)
                            elif interval == dateutil.relativedelta.relativedelta(years=1):
                                j_range_start, j_range_end = jdate_utils.get_year(j_range_start)
                            j_range_end += jdatetime.timedelta(seconds=1) # because of using "<" operator in the domain

                            if MODELS.READ_GROUP_DISPLAY_FORMAT[granularity] == 'dd MMM yyyy':
                                label = str(j_range_start.year) + ' ' + jdate_utils.get_month_name(j_range_start, locale) + ' ' + str(j_range_start.day)
                            elif MODELS.READ_GROUP_DISPLAY_FORMAT[granularity] == "'W'w YYYY":
                                label = ('W' if locale == 'en_US' else 'ه‌') + str(j_range_start.weeknumber()) + ' ' + str(j_range_start.year)
                            elif MODELS.READ_GROUP_DISPLAY_FORMAT[granularity] == 'MMMM yyyy':
                                label = jdate_utils.get_month_name(j_range_start, locale) + ' ' + str(j_range_start.year)
                            elif MODELS.READ_GROUP_DISPLAY_FORMAT[granularity] == 'QQQ yyyy':
                                label = jdate_utils.get_quarter_name(j_range_start, locale) + ' ' + str(j_range_start.year)
                            elif MODELS.READ_GROUP_DISPLAY_FORMAT[granularity] == 'yyyy':
                                label = str(j_range_start.year)

                            range_start = pytz.timezone(self._context.get('tz', 'UTC')).localize(jdatetime.datetime.togregorian(j_range_start))
                            range_end = pytz.timezone(self._context.get('tz', 'UTC')).localize(jdatetime.datetime.togregorian(j_range_end))

                            ########## ######### ##########

                            range_start = range_start.strftime(fmt)
                            range_end = range_end.strftime(fmt)
                            row[group] = label  # TODO should put raw data
                            row.setdefault('__range', {})[group] = {'from': range_start, 'to': range_end}
                            additional_domain = [
                                '&',
                                    (field_name, '>=', range_start),
                                    (field_name, '<', range_end),
                            ]
                        elif not value:
                            # Set the __range of the group containing records with an unset
                            # date/datetime field value to False.
                            row.setdefault('__range', {})[group] = False

                    row['__domain'] = expression.AND([row['__domain'], additional_domain])
        else:
            super()._read_group_format_result(rows_dict, lazy_groupby)