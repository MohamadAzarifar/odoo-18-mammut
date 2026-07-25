# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _
from odoo.exceptions import UserError

from datetime import datetime
import pytz
import jdatetime

class artaradIrSequence(models.Model):
    _inherit = 'ir.sequence'

    # Overrided methods
    def _get_prefix_suffix(self, date=None, date_range=None):
        def _interpolate(s, d):
            return (s % d) if s else ''

        def _interpolation_dict():
            now = range_date = effective_date = datetime.now(pytz.timezone(self._context.get('tz') or 'UTC'))
            if date or self._context.get('ir_sequence_date'):
                effective_date = fields.Datetime.from_string(date or self._context.get('ir_sequence_date'))
            if date_range or self._context.get('ir_sequence_date_range'):
                range_date = fields.Datetime.from_string(date_range or self._context.get('ir_sequence_date_range'))

            ################################overrided part################################
            '''
            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S'
            }
            res = {}
            for key, format in sequences.items():
                res[key] = effective_date.strftime(format)
                res['range_' + key] = range_date.strftime(format)
                res['current_' + key] = now.strftime(format)
            '''
            sequences = {
                'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j', 'woy': '%W',
                'weekday': '%w', 'h24': '%H', 'h12': '%I', 'min': '%M', 'sec': '%S',

                'jyear': '%Y', 'jy': '%y', 'jmonth': '%m', 'jday': '%d', 'jdoy': '%j', 'jwoy': '%W', 'jweekday': '%w', 'jh24': '%H', 'jh12': '%I', 'jmin': '%M', 'jsec': '%S',
            }
            res = {}
            for key, format in sequences.items():
                if key[0] == 'j':
                    res[key] = jdatetime.datetime.fromgregorian(date=effective_date).replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Tehran')).strftime(format)
                    res['range_' + key] = jdatetime.datetime.fromgregorian(date=range_date).replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Tehran')).strftime(format)
                    res['current_' + key] = jdatetime.datetime.fromgregorian(date=now).replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Tehran')).strftime(format)
                else:
                    res[key] = effective_date.strftime(format)
                    res['range_' + key] = range_date.strftime(format)
                    res['current_' + key] = now.strftime(format)
            ##############################################################################
            return res

        d = _interpolation_dict()
        try:
            interpolated_prefix = _interpolate(self.prefix, d)
            interpolated_suffix = _interpolate(self.suffix, d)
        except ValueError:
            raise UserError(_('Invalid prefix or suffix for sequence \'%s\'') % (self.get('name')))
        return interpolated_prefix, interpolated_suffix