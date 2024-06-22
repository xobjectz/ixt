# This file is placed in the Public Domain.
#
# pylint: disable=R0903


"udp to irc relay"


import select
import socket
import sys
import threading
import time


from tix.object import Object, fmt
from tix.log    import debug
from tix.thread import launch
from tix.run    import broker


def init():
    "initialize udp to irc relay."
    udpd = UDP()
    udpd.start()
    debug(f"started udp {fmt(Config)}")
    return udpd


class Config(Object):

    "Cfg"

    addr = ""
    host = "localhost"
    port = 5500


class UDP(Object):

    "UDP"

    def __init__(self):
        Object.__init__(self)
        self.stopped = False
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.setblocking(1)
        self._starttime = time.time()
        self.ready = threading.Event()

    def output(self, txt, addr=None):
        "annouce on bots."
        if addr:
            Config.addr = addr
        for name, bot in broker.all("irc"):
            print("yo!")
            bot.announce(txt.replace("\00", ""))

    def loop(self):
        "run input loop."
        try:
            self._sock.bind((Config.host, Config.port))
        except socket.gaierror:
            return
        self.ready.set()
        while not self.stopped:
            (txt, addr) = self._sock.recvfrom(64000)
            if self.stopped:
                break
            data = str(txt.rstrip(), "utf-8")
            if not data:
                break
            self.output(data, addr)

    def exit(self):
        "stop relay."
        self.stopped = True
        self._sock.settimeout(0.01)
        self._sock.sendto(
                          bytes("exit", "utf-8"),
                          (Config.host, Config.port)
                         )

    def start(self):
        "start relay."
        launch(self.loop)


def toudp(host, port, txt):
    "send udp to bot."
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(bytes(txt.strip(), "utf-8"), (host, port))


def udp(event):
    "relay text to bots."
    if event.rest:
        toudp(Config.host, Config.port, event.rest)
        debug(f"{len(event.rest)} characters sent")
        return
    if not select.select(
                         [sys.stdin, ],
                         [],
                         [],
                         0.0
                        )[0]:
        return
    size = 0
    while 1:
        try:
            (inp, _out, err) = select.select(
                                             [sys.stdin,],
                                             [],
                                             [sys.stderr,]
                                            )
        except KeyboardInterrupt:
            return
        if err:
            break
        stop = False
        for sock in inp:
            txt = sock.readline()
            if not txt:
                stop = True
                break
            size += len(txt)
            toudp(Config.host, Config.port, txt)
        if stop:
            break
