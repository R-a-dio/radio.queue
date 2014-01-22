from __future__ import absolute_import
import functools
import socket

import jsonrpclib

from .server import create_entry


def entrify(function):
    @functools.wraps(function)
    def entrified(*args, **kwargs):
        res = function(*args, **kwargs)

        if isinstance(res, dict):
            res = create_entry(**res)
        elif isinstance(res, list):
            for i, item in enumerate(res):
                res[i] = create_entry(**item)

        return res

    return entrified
def propagate_exceptions(function):
    @functools.wraps(function)
    def exception_handler(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except jsonrpclib.jsonrpc.ProtocolError as err:
            message = err.message[1]
            if '|' in message:
                message = message.split('|', 1)[1]

            raise QueueError(message)
        except socket.error as err:
            raise QueueError("Failed to connect.")

    return exception_handler


class QueueError(Exception):
    pass


class JSONExceptionHandler(type):
    def __new__(cls, name, bases, dct):
        for key, value in dct.iteritems():
            if callable(value):
                dct[key] = propagate_exceptions(value)

        return type.__new__(cls, name, bases, dct)


class Queue(object):
    __metaclass__ = JSONExceptionHandler

    def __init__(self, url=None):
        super(Queue, self).__init__()
        self.server = jsonrpclib.Server(url)

    @entrify
    def peek(self, index=0):
        return self.server.peek(index=index)

    @entrify
    def pop(self):
        return self.server.pop()

    def append(self, song):
        return self.server.append(song)

    def append_request(self, song):
        return self.server.append_request(song)

    @entrify
    def __getitem__(self, point):
        if isinstance(point, slice):
            return self.server.slice(start=point.start, end=point.stop)
        elif isinstance(point, int):
            return self.server.peek(point)
        return None

    def __len__(self):
        return self.server.length()

    @entrify
    def __iter__(self):
        return self[0:len(self)]