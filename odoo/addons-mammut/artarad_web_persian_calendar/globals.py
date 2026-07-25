import datetime
import jdatetime
import dateutil
import math


class jdate_utils:

    @staticmethod
    def get_year(dt):
        dt_from = jdatetime.datetime(dt.year, 1, 1)
        dt_to = jdatetime.datetime(dt.year+1, 1, 1) - jdatetime.timedelta(seconds=1)

        return dt_from, dt_to


    @staticmethod
    def get_quarter(dt):
        quarter_number = jdate_utils.get_quarter_number(dt)

        month_from = ((quarter_number - 1) * 3) + 1
        dt_from = jdatetime.datetime(dt.year, month_from, 1)

        if quarter_number == 1 or quarter_number == 2:
            dt_to = jdatetime.datetime(dt.year, month_from+2, 31, 23, 59, 59)
        elif quarter_number == 3:
            dt_to = jdatetime.datetime(dt.year, month_from+2, 30, 23, 59, 59)
        else:
            if dt.isleap():
                dt_to = jdatetime.datetime(dt.year, month_from+2, 30, 23, 59, 59)
            else:
                dt_to = jdatetime.datetime(dt.year, month_from+2, 29, 23, 59, 59)

        return dt_from, dt_to


    @staticmethod
    def get_month(dt):
        dt_from = jdatetime.datetime(dt.year, dt.month, 1)

        if dt.month <= 6:
            dt_to = jdatetime.datetime(dt.year, dt.month, 31, 23, 59, 59)
        elif dt.month <= 11:
            dt_to = jdatetime.datetime(dt.year, dt.month, 30, 23, 59, 59)
        else:
            if dt.isleap():
                dt_to = jdatetime.datetime(dt.year, dt.month, 30, 23, 59, 59)
            else:
                dt_to = jdatetime.datetime(dt.year, dt.month, 29, 23, 59, 59)
        return dt_from, dt_to


    @staticmethod
    def get_week(dt):
        dt_from = jdatetime.datetime(dt.year, dt.month, dt.day)
        while dt_from.weekday() != 0:
            dt_from -= jdatetime.timedelta(days=1)
        
        dt_to = (dt_from + jdatetime.timedelta(days=6)).replace(hour=23, minute=59, second=59)

        return dt_from, dt_to


    @staticmethod
    def get_day(dt):
        dt_from = jdatetime.datetime(dt.year, dt.month, dt.day)
        dt_to = dt_from.replace(hour=23, minute=59, second=59)

        return dt_from, dt_to


    @staticmethod
    def get_quarter_number(dt):
        return math.ceil(dt.month / 3)


    @staticmethod
    def get_quarter_name(dt, lang):
        if lang == 'en_US':
            quarter_names = {1: 'Spring', 2: 'Summer', 3: 'Fall', 4: 'Winter'}
        else:
            quarter_names = {1: 'بهار', 2: 'تابستان', 3: 'پاییز', 4: 'زمستان'}
        return quarter_names[jdate_utils.get_quarter_number(dt)]


    @staticmethod
    def get_month_name(dt, lang):
        if lang == 'en_US':
            month_names = {1: 'Farvardin', 2: 'Ordibehesht', 3: 'Khordad', 4: 'Tir', 5: 'Mordad', 6: 'Shahrivar', 7: 'Mehr', 8: 'Aban', 9: 'Azar', 10: 'Dey', 11: 'Bahman', 12: 'Esfand'}
        else:
            month_names = {1:"فروردین", 2:"اردیبهشت", 3:"خرداد", 4:"تیر", 5:"مرداد", 6:"شهریور", 7:"مهر", 8:"آبان", 9:"آذر", 10:"دی", 11:"بهمن", 12:"اسفند"}
        return month_names[dt.month]


    @staticmethod
    def get_weekday_name(dt, lang):
        if lang == 'en_US':
            weekday_names = {1: 'Saturday', 2: 'Sunday', 3: 'Monday', 4: 'Tuesday', 5: 'Wednesday', 6: 'Thursday', 7: 'Friday'}
        else:
            weekday_names = {1: 'شنبه', 2: 'یک‌شنبه', 3: 'دوشنبه', 4: 'سه‌شنبه', 5: 'چهارشنبه', 6: 'پنج‌شنبه', 7: 'جمعه'}
        return weekday_names[dt.weekday() + 1]

    @staticmethod
    def get_next_month(dt):
        year = dt.year if dt.month <= 11 else dt.year + 1
        month = dt.month + 1 if dt.month <= 11 else 1
        if jdate_utils.is_last_day_of_month(dt):
            day = jdate_utils.get_month(jdatetime.datetime(year, month, 1))[1].day
        else:
            day = dt.day

        return jdatetime.datetime(year, month, day, dt.hour, dt.minute, dt.second, tzinfo=dt.tzinfo) if isinstance(dt, jdatetime.datetime) else jdatetime.date(year, month, day)

    @staticmethod
    def get_previous_month(dt):
        year = dt.year if dt.month >= 2 else dt.year - 1
        month = dt.month - 1 if dt.month >= 2 else 12
        if jdate_utils.is_last_day_of_month(dt):
            day = jdate_utils.get_month(jdatetime.datetime(year, month, 1))[1].day
        else:
            day = dt.day

        return jdatetime.datetime(year, month, day, dt.hour, dt.minute, dt.second, tzinfo=dt.tzinfo) if isinstance(dt, jdatetime.datetime) else jdatetime.date(year, month, day)

    @staticmethod
    def get_date_range(start, end, step):
        def get_timedelta(dt, step):
            if step == dateutil.relativedelta.relativedelta(days=1):
                return jdatetime.timedelta(days=1)
            elif step == datetime.timedelta(7):
                return jdatetime.timedelta(days=7)                            
            elif step == dateutil.relativedelta.relativedelta(months=1):
                return jdate_utils.get_next_month(dt) - dt
            elif step == dateutil.relativedelta.relativedelta(months=3):
                delta = 0
                temp_dt = dt
                for _ in range(3):
                    next_month = jdate_utils.get_next_month(temp_dt)
                    delta += (next_month - temp_dt).days
                    temp_dt = next_month
                return jdatetime.timedelta(days=delta)
            elif step == dateutil.relativedelta.relativedelta(years=1):
                return dt.replace(year=dt.year+1) - dt

        result = []
        dt = start
        while dt <= end:
            result.append(dt)
            dt += get_timedelta(dt, step)
        return result
    
    @staticmethod
    def is_last_day_of_month(dt):
        return dt.day == jdate_utils.get_month(jdatetime.datetime(dt.year, dt.month, 1))[1].day
