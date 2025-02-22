# This file is placed in the Public Domain.
#
# pylint: disable=R0912


"timer"


import datetime
import re
import time as ttime


from ..event  import Event
from ..object import update
from ..run    import broker
from ..timer  import Timer
from ..utils  import laps
from ..thread import launch


def init():
    "initialaze modules."
    for _fnm, obj in broker.all("timer"):
        diff = float(obj.time) - ttime.time()
        if diff > 0:
            bot = broker.first("timer")
            evt = Event()
            update(evt, obj)
            evt.orig = repr(bot)
            timer = Timer(diff, evt.show)
            launch(timer.start)


MONTHS = [
    'Bo',
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec'
]


FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d-%m",
    "%m-%d",
]


class NoDate(Exception):

    "can't parse date."


def extract_date(daystr):
    "extract date from string."
    res = None
    for fmt in FORMATS:
        try:
            res = ttime.mktime(ttime.strptime(daystr, fmt))
            break
        except ValueError:
            pass
    return res


def get_day(daystr):
    "return day from string."
    day = None
    month = None
    yea = None
    try:
        ymdre = re.search(r'(\d+)-(\d+)-(\d+)', daystr)
        if ymdre:
            (day, month, yea) = ymdre.groups()
    except ValueError:
        try:
            ymre = re.search(r'(\d+)-(\d+)', daystr)
            if ymre:
                (day, month) = ymre.groups()
                yea = ttime.strftime("%Y", ttime.localtime())
        except Exception as ex:
            raise NoDate(daystr) from ex
    if day:
        day = int(day)
        month = int(month)
        yea = int(yea)
        date = f"{day} {MONTHS[month]} {yea}"
        return ttime.mktime(ttime.strptime(date, r"%d %b %Y"))
    raise NoDate(daystr)


def get_hour(daystr):
    "get hour from string."
    try:
        hmsre = re.search(r'(\d+):(\d+):(\d+)', str(daystr))
        hours = 60 * 60 * (int(hmsre.group(1)))
        hoursmin = hours  + int(hmsre.group(2)) * 60
        hmsres = hoursmin + int(hmsre.group(3))
    except AttributeError:
        pass
    except ValueError:
        pass
    try:
        hmre = re.search(r'(\d+):(\d+)', str(daystr))
        hours = 60 * 60 * (int(hmre.group(1)))
        hmsres = hours + int(hmre.group(2)) * 60
    except AttributeError:
        return 0
    except ValueError:
        return 0
    return hmsres


def get_time(txt):
    "return time from string."
    try:
        target = get_day(txt)
    except NoDate:
        target = to_day(today())
    hour =  get_hour(txt)
    if hour:
        target += hour
    return target


def parse_time(txt):
    "parse time from string."
    seconds = 0
    target = 0
    txt = str(txt)
    for word in txt.split():
        if word.startswith("+"):
            seconds = int(word[1:])
            return ttime.time() + seconds
        if word.startswith("-"):
            seconds = int(word[1:])
            return ttime.time() - seconds
    if not target:
        try:
            target = get_day(txt)
        except NoDate:
            target = to_day(today())
        hour =  get_hour(txt)
        if hour:
            target += hour
    return target


def to_day(daystr):
    "scan string for day/time."
    previous = ""
    line = ""
    daystr = str(daystr)
    res = None
    for word in daystr.split():
        line = previous + " " + word
        previous = word
        try:
            res = extract_date(line.strip())
        except ValueError:
            res = None
        if res:
            break
        line = ""
    return res

def today():
    "return time of today."
    return str(datetime.datetime.today()).split()[0]


def tmr(event):
    "set timer."
    res = None
    if not event.rest:
        nmr = 0
        for _fnm, obj in broker.all('timer'):
            lap = float(obj.time) - ttime.time()
            if lap > 0:
                event.reply(f'{nmr} {obj.txt} {laps(lap)}')
                nmr += 1
        if not nmr:
            event.reply("no timers")
        return res
    seconds = 0
    line = ""
    for word in event.args:
        if word.startswith("+"):
            try:
                seconds = int(word[1:])
            except (ValueError, IndexError):
                event.reply(f"{seconds} is not an integer")
                return res
        else:
            line += word + " "
    if seconds:
        target = ttime.time() + seconds
    else:
        try:
            target = get_day(event.rest)
        except NoDate:
            target = to_day(today())
        hour =  get_hour(event.rest)
        if hour:
            target += hour
    if not target or ttime.time() > target:
        event.reply("already passed given time.")
        return res
    bot = broker.get(event.orig)
    event.time = target
    diff = target - ttime.time()
    event.result = []
    event.reply("ok " +  laps(diff))
    event.result.append(event.rest)
    timer = Timer(diff, bot.show, event, thrname=event.cmd)
    update(timer, event)
    launch(timer.start)
    return res
