# This file is placed in the Public Domain.
#
# pylint: disable=R0903


"rich site syndicate"


import html
import html.parser
import re
import time
import urllib
import urllib.request
import _thread


from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode


from ..default  import Default
from ..object   import Object, fmt, update, values
from ..persist  import find, last, sync
from ..repeater import Repeater
from ..thread   import launch
from ..run      import broker
from ..utils    import fntime, laps, spl


def init():
    "start fetcher."
    fetcher = Fetcher()
    fetcher.start()
    return fetcher


DEBUG = False


fetchlock = _thread.allocate_lock()


class Feed(Default):

    "Feed"



class Rss(Default):

    "Rss"

    def __init__(self):
        Default.__init__(self)
        self.display_list = 'title,link,author'
        self.rss          = ''


class Seen(Default):

    "Seen"

    def __init__(self):
        Default.__init__(self)
        self.urls = []


class Fetcher(Object):

    "Fetcher"

    def __init__(self):
        self.dosave = False
        self.seen = Seen()
        self.seenfn = None
        broker.register(self)

    @staticmethod
    def display(obj):
        "display object."
        result = ''
        displaylist = []
        try:
            displaylist = obj.display_list or 'title,link'
        except AttributeError:
            displaylist = 'title,link,author'
        for key in displaylist.split(","):
            if not key:
                continue
            data = getattr(obj, key, None)
            if not data:
                continue
            data = data.replace('\n', ' ')
            data = striphtml(data.rstrip())
            data = unescape(data)
            result += data.rstrip()
            result += ' - '
        return result[:-2].rstrip()

    def fetch(self, feed, silent=False):
        "fetch feed."
        with fetchlock:
            counter = 0
            result = []
            for obj in reversed(getfeed(feed.rss, feed.display_list)):
                fed = Feed()
                update(fed, obj)
                update(fed, feed)
                url = urllib.parse.urlparse(fed.link)
                if url.path and not url.path == '/':
                    uurl = f'{url.scheme}://{url.netloc}/{url.path}'
                else:
                    uurl = fed.link
                if uurl in self.seen.urls:
                    continue
                self.seen.urls.append(uurl)
                counter += 1
                if self.dosave:
                    sync(fed)
                result.append(fed)
        if silent:
            return counter
        txt = ''
        feedname = getattr(feed, 'name', None)
        if feedname:
            txt = f'[{feedname}] '
        for obj in result:
            txt2 = txt + self.display(obj)
            for bot in values(broker.objs):
                if "announce" in dir(bot):
                    bot.announce(txt2.rstrip())
        return counter

    def run(self, silent=False):
        "fetch all feeds."
        thrs = []
        for _fn, feed in find('rss'):
            thrs.append(launch(self.fetch, feed, silent, name=f"{feed.rss}"))
        return thrs

    def start(self, repeat=True):
        "start fetcher."
        self.seenfn = last(self.seen)
        if repeat:
            repeater = Repeater(300.0, self.run)
            repeater.start()


class Parser:

    "Parser"

    @staticmethod
    def getitem(line, item):
        "match items."
        lne = ''
        index1 = line.find(f'<{item}>')
        if index1 == -1:
            return lne
        index1 += len(item) + 2
        index2 = line.find(f'</{item}>', index1)
        if index2 == -1:
            return lne
        lne = line[index1:index2]
        lne = cdata(lne)
        return lne.strip()

    @staticmethod
    def getitems(text, token):
        "loop for items."
        index = 0
        result = []
        stop = False
        while not stop:
            index1 = text.find(f'<{token}', index)
            if index1 == -1:
                break
            index1 += len(token) + 2
            index2 = text.find(f'</{token}>', index1)
            if index2 == -1:
                break
            lne = text[index1:index2]
            result.append(lne)
            index = index2
        return result

    @staticmethod
    def parse(txt, toke="item", items='title,link'):
        "parse a text for tokens."
        result = []
        for line in Parser.getitems(txt, toke):
            line = line.strip()
            obj = Default()
            for itm in spl(items):
                val = Parser.getitem(line, itm)
                if val:
                    val = unescape(val.strip())
                    val = val.replace("\n", "")
                    val = striphtml(val)
                    setattr(obj, itm, val)
            result.append(obj)
        return result


def getfeed(url, items):
    "fetch a feed."
    result = [Object(), Object()]
    if DEBUG:
        return result
    try:
        rest = geturl(url)
    except (ValueError, HTTPError, URLError):
        return result
    if rest:
        if url.endswith('atom'):
            result = Parser.parse(str(rest.data, 'utf-8'), 'entry', items) or []
        else:
            result = Parser.parse(str(rest.data, 'utf-8'), 'item', items) or []
    return result


def gettinyurl(url):
    "fetch a tinyurl."
    postarray = [
        ('submit', 'submit'),
        ('url', url),
    ]
    postdata = urlencode(postarray, quote_via=quote_plus)
    req = urllib.request.Request('http://tinyurl.com/create.php',
                  data=bytes(postdata, 'UTF-8'))
    req.add_header('User-agent', useragent("rss fetcher"))
    with urllib.request.urlopen(req) as htm: # nosec
        for txt in htm.readlines():
            line = txt.decode('UTF-8').strip()
            i = re.search('data-clipboard-text="(.*?)"', line, re.M)
            if i:
                return i.groups()
    return []


def cdata(line):
    "retrieve text from CDATA."
    if 'CDATA' in line:
        lne = line.replace('![CDATA[', '')
        lne = lne.replace(']]', '')
        lne = lne[1:-1]
        return lne
    return line


def geturl(url):
    "fetch a url."
    if not url.startswith("http://") and not url.startswith("https://"):
        return ""
    url = urllib.parse.urlunparse(urllib.parse.urlparse(url))
    req = urllib.request.Request(url)
    req.add_header('User-agent', useragent("rss fetcher"))
    with urllib.request.urlopen(req) as response: # nosec
        response.data = response.read()
        return response


def striphtml(text):
    "strip html."
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def unescape(text):
    "unescape text."
    txt = re.sub(r'\s+', ' ', text)
    return html.unescape(txt)


def useragent(txt):
    "return useragent."
    return 'Mozilla/5.0 (X11; Linux x86_64) ' + txt


def dpl(event):
    "set display items."
    if len(event.args) < 2:
        event.reply('dpl <stringinurl> <item1,item2>')
        return
    setter = {'display_list': event.args[1]}
    for _fn, feed in find("rss", {'rss': event.args[0]}):
        if feed:
            update(feed, setter)
    event.reply('ok')


def nme(event):
    "set name of feed."
    if len(event.args) != 2:
        event.reply('nme <stringinurl> <name>')
        return
    selector = {'rss': event.args[0]}
    for _fn, feed in find("rss", selector):
        if feed:
            feed.name = event.args[1]
    event.reply('ok')


def rem(event):
    "remove a feed."
    if len(event.args) != 1:
        event.reply('rem <stringinurl>')
        return
    for _fnm, feed in find("rss"):
        if event.args[0] not in feed.rss:
            continue
        if feed:
            feed.__deleted__ = True
    event.reply('ok')


def res(event):
    "restore a feed."
    if len(event.args) != 1:
        event.reply('res <stringinurl>')
        return
    for fnm, feed in find("rss", None, True):
        if event.args[0] not in feed.rss:
            continue
        if feed:
            feed.__deleted__ = False
            sync(feed, fnm)
    event.reply('ok')


def rss(event):
    "add a feed."
    if not event.rest:
        nrs = 0
        for fnm, feed in find('rss'):
            nrs += 1
            elp = laps(time.time()-fntime(fnm))
            txt = fmt(feed)
            event.reply(f'{nrs} {txt} {elp}')
        if not nrs:
            event.reply('no rss feed found.')
        return
    url = event.args[0]
    if 'http' not in url:
        event.reply('i need an url')
        return
    for fnm, result in find("rss", {'rss': url}):
        if result:
            event.reply(f'already got {url}')
            return
    feed = Rss()
    feed.rss = event.args[0]
    sync(feed)
    event.reply('ok')


def syn(event):
    "synchronize feeds."
    fetchers = list(broker.all("fetcher"))
    if not fetchers:
        event.reply("no fetcher found.")
        return
    fetcher = fetchers[0][-1]
    thrs = fetcher.run(True)
    nrs = 0
    for thr in thrs:
        thr.join()
        nrs += 1
    event.reply(f"{nrs} feeds synced")
