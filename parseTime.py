"""
Convert a string to a python datetime.

Below are sample inputs that should work once everyting is done.

- absolute dates
january10
jan10

- absolute days and times
wednesday
wed
tomorrow

- relative
1h
1hour
2hours
1d
1day
2days
1w
1week
1weeks
1m
1month
1months
1year
1y
1years
-> any combination of the above

"""

import re
import datetime
import logging
logging.getLogger().setLevel('DEBUG')

from dateutil.relativedelta import relativedelta
from dateutil.tz import *

relativeRegex = r'''
    ^
    (?P<number>\d+)                                                 # number of days/months/...
    (?P<type>year|y|month|week|w|day|d|hour|h|minute|min|m)         # days/months/...
    s?                                                              # accept day or days
    (?P<remainingString>.*)                                         # will be searched recursively
    $
    '''
dayRegex = r'''
    ^
    (?P<day>monday|mon|tuesday|tue|wednesday|wed|thursday|thu|
        friday|fri|saturday|sat|sunday|sun|tomorrow)    # either weekday or tomorrow
    (?P<time>\d{1,2}(?:am|pm|h)|)                             # 9pm same as 21h, not used currently
    $
    '''
dateRegex = r'''
    ^
    (?P<month>jan|january|feb|february|mar|march|apr|april|may|
        jun|june|jul|july|aug|august|sep|september|oct|october|nov|
        november|dec|december)                                         # month
    (?P<day>\d{1,2})                                                   # day of the month
    $
    '''

def relativeTimeInString(timeString):
    # recursively extract relative time data from 
    # string, returns list of tuples like [(2, 'months')]
    relMatches = re.match(relativeRegex, timeString, re.VERBOSE)
    if relMatches:
        return ([relMatches.group('number', 'type')] +
            relativeTimeInString(relMatches.group('remainingString')))
    return []

def shiftTime(amount, timeType, timepoint):
    amount = int(amount)
    if timeType in ('year','y', 'years'):
        timeType = 'years'
    elif timeType in ('month','m', 'months'):
        timeType = 'months'
    elif timeType in ('week', 'w', 'weeks'):
        timeType = 'weeks'
    elif timeType in ('day', 'd', 'days'):
        timeType = 'days'
    elif timeType in ('hour', 'h', 'hours'):
        timeType = 'hours'
    elif timeType in ('minute', 'min', 'minutes'):
        timeType = 'minutes'
    else:
        raise ValueError('Time type %s not known' % timeType)
    return timepoint + relativedelta(**{timeType:amount})

def recognizeMonth(monthString):
    if monthString in ('jan', 'january'):
        return 1
    elif monthString in ('feb', 'february'):
        return 2
    elif monthString in ('mar', 'march'):
        return 3
    elif monthString in ('apr', 'april'):
        return 4
    elif monthString in ('may'):
        return 5
    elif monthString in ('jun', 'june'):
        return 6
    elif monthString in ('jul', 'july'):
        return 7
    elif monthString in ('aug', 'august'):
        return 8
    elif monthString in ('sep', 'september'):
        return 9
    elif monthString in ('oct', 'october'):
        return 10
    elif monthString in ('nov', 'november'):
        return 11
    elif monthString in ('dec', 'december'):
        return 12
    raise Exception('no month detected')

def constructDatetimeFromRelativeTimeInString(timeString, timezoneObject):
    relMatches = relativeTimeInString(timeString)
    if not relMatches:
        return None
    # unpack tuples and add timedeltas to current time.
    timepoint = datetime.datetime.now(timezoneObject)
    for amount, timeType in relMatches:
        timepoint = shiftTime(amount, timeType, timepoint) 
    return timepoint

def constructDatetimeFromDateString(timeString, timezoneObject, startOfDay):
    # check for dates of type 'march30'
    dateMatch = re.match(dateRegex, timeString, re.VERBOSE)
    if not dateMatch:
        return None
    month, day = dateMatch.group('month', 'day')
    m = recognizeMonth(month)
    d = int(day)
    # guess year: current year or next year?
    now = datetime.datetime.now(timezoneObject)
    y = now.year
    if m < now.month or (m == now.month and day < now.day):
        y+=1
    timepoint = datetime.datetime(y,m,d,startOfDay,0,0,0,timezoneObject)
    return timepoint

def shiftToWeekday(day, timepoint):
    if day in ('mon', 'monday'):
        d=0
    elif day in ('tue', 'tuesday'):
        d=1
    elif day in ('wed', 'wednesday'):
        d=2
    elif day in ('thu', 'thursday'):
        d=3
    elif day in ('fri', 'friday'):
        d=4
    elif day in ('sat', 'saturday'):
        d=5
    elif day in ('sun', 'sunday'):
        d=6
    else:
        raise Exception('could not recognize weekday %s' % day)
    daysToAdd = d - timepoint.weekday()
    # set to next week if day is same as today
    if daysToAdd <= 0:
        daysToAdd += 7
    return timepoint + datetime.timedelta(daysToAdd)


def constructDatetimeFromDayString(timeString, timezoneObject, startOfDay):
    # check for absolute dates/times of type 'tomorrow3am'
    dayMatches = re.match(dayRegex, timeString, re.VERBOSE)
    if not dayMatches:
        return None
    # warning: also matches '' and impossible times
    now = datetime.datetime.now(timezoneObject)
    day, time = dayMatches.group('day', 'time')
    if (day == 'tomorrow'):
        timepoint = now + datetime.timedelta(1)
    else:
        # assume day is a weekday
        timepoint = shiftToWeekday(day, now)
    # set 7am or whatever time is start of the day
    timepoint = timepoint.replace(hour=startOfDay,minute=0,second=0,microsecond=0)
    return timepoint



def parseTime(timeString, timezoneObject, startOfDay):
    # everything is case-insensitive
    timeString = timeString.lower()
    # check for dates of type 'march30'
    timepoint = constructDatetimeFromDateString(timeString, timezoneObject, startOfDay)
    if timepoint:
        logging.info('recognized date: %s from %s' % (timepoint, timeString))
        return (timepoint, startOfDay)
    # check for relative time of type '1year2months'
    timepoint = constructDatetimeFromRelativeTimeInString(timeString, timezoneObject)
    if timepoint:
        logging.info('recognized relative time: %s from %s' % (timepoint, timeString))
        return (timepoint, None)
    # check for absolute dates/times of type 'tomorrow3am'
    timepoint = constructDatetimeFromDayString(timeString, timezoneObject, startOfDay)
    if timepoint:
        # warning: also matches '' and impossible times
        logging.info('recognized day: %s from %s' % (timepoint, timeString))
        return (timepoint, startOfDay)
    logging.warning('no time recognized: %s' % timeString)
    return (None, None)