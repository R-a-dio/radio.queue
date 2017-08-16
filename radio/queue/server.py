from __future__ import absolute_import
import functools
import threading
import time
import logging
import sys
from collections import deque, namedtuple

from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer as JSONServer
import jsonrpclib


# setup logging, we use stdout
logger = logging.getLogger("radio.queue")
logger.addHandler(logging.StreamHandler(sys.stderr))

jsonrpclib.config.use_jsonclass = False

api_functions = []
Backend = namedtuple("Backend", ("save", "load", "populate", "expand", "length"))

# We need a backend we can return at all times. This one always just does nothing.
NOP = lambda *args, **kwargs: None
NOP_BACKEND = Backend(save=NOP, load=NOP, populate=NOP, expand=NOP, length=NOP)

# A dictionary of backends, name => Backend
backends = {}


class Entry(dict):
    _fields = ("songid", "length", "metadata", "filename", "request", "estimate")

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return super(Entry, self).__getattr__(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        del self[key]


# Inherit from deque here so we can add our own attributes to instances.
class deque(deque):
    def append(self, item):
        item.estimate = self.next_song_estimate
        for entry in self:
            item.estimate += entry.length

        item = find_backend(self.backend).expand(self, item)

        super(deque, self).append(item)


def public(function):
    """
    Decorator to expose a function to the JSON RPC clients
    """
    if function not in api_functions:
        api_functions.append(function)
    return function


def commit(function):
    @functools.wraps(function)
    def save_after_execution(queue, *args, **kwargs):
        try:
# This is terribly broken because the assumption is that the memory
# queue is the master and the backend is just a store. No assumption
# about the state of the backend can be made, and it does not have to
# be consistent with the memory queue.
#            with queue.lock:
#                # Check that the lengths of the internal queue
#                # and the backend store queue match up.
#                backend_len = find_backend(queue.backend).length(queue)
#                if len(queue) != backend_len:
#                    logger.debug("length mismatch(%d, %d), reloading", len(queue), backend_len)
#
#                    # If they don't, purge the internal queue and reload.
#                    queue.clear()
#                    load(queue)
#                    populate(queue)
#
            return function(queue, *args, **kwargs)
        finally:
            run(save, queue)

    return save_after_execution


def normalize(song):
    """
    Takes a dictionary and fixes it to only have keys that
    are fields on the `Entry` namedtuple.
    """
    plain = {key: None for key in Entry._fields}

    for key, value in song.iteritems():
        if key in plain:
            plain[key] = value

    return plain


def create_entry(**song):
    """
    Returns a new Entry instance.
    """
    song = normalize(song)

    return Entry(**song)


@public
@commit
def pop(queue):
    """
    Pops an item from the queue and returns it
    """
    with queue.lock:
        entry = queue.popleft()

        logger.debug("pop: %s", entry)
        queue.next_song_estimate = time.time() + entry.length

        run(populate, queue)

        return entry


@public
def peek(queue, index=0):
    """
    Peeks at an index of the queue, returns the entry
    found at said index.
    """
    with queue.lock:
        try:
            return queue[index]
        except IndexError:
            return None


@public
@commit
def append(queue, song):
    """
    Appends an Entry to the queue
    """
    entry = create_entry(**song)

    with queue.lock:
        queue.append(entry)

    logger.debug("append: %s", song)


@public
@commit
def append_request(queue, song):
    """
    Appends an Entry and forces `request=True`
    """
    song['request'] = True

    entry = create_entry(**song)

    with queue.lock:
        queue.append(entry)

    logger.debug("append_request: %s", song)


@public
def slice(queue, start=0, end=None):
    """
    Returns part of the queue.

    Returns the full length queue if both arguments
    are kept as their default value.
    """
    end = end if end is not None else len(queue)

    with queue.lock:
        return list(queue)[start:end]


@public
def length(queue):
    return len(queue)


def save(queue, backend=None):
    """
    Saves the queue.
    """
    backend = backend or queue.backend

    logger.info("saving queue")
    return find_backend(backend).save(queue)


def load(queue, backend=None):
    """
    Populates `queue` with a previous save.
    """
    backend = backend or queue.backend

    queue.next_song_estimate = time.time()

    logger.info("loading queue")
    return find_backend(backend).load(queue)


def populate(queue, backend=None):
    """
    Populates any missing entries in the queue.
    """
    backend = backend or queue.backend

    logger.info("populating queue")
    return find_backend(backend).populate(queue)


def run_server(host, port, backend="mysql", config=None):
    logger.setLevel(logging.DEBUG)

    logger.info("initializing in-memory queue")
    # Create our local queue
    queue = deque()
    queue.backend = backend
    queue.config = config or {}
    queue.lock = threading.RLock()

    # Load any queue we've had active previously
    load(queue)
    # Make sure the queue is populated enough to be used
    populate(queue)

    # Create copies of the API methods with our local queue applied
    functions = wrap_functions(queue)

    logger.info("initializing jsonrpc server")
    # Setup the JSON RPC server and its methods
    server = JSONServer((host, port), encoding="utf8", logRequests=False)

    for function in functions:
        logger.debug("-> registering jsonrpc function: %s", function)
        server.register_function(function)

    logger.info("starting jsonrpc server")
    server.serve_forever()

    # Save before exiting
    save(queue)

    logger.info("exiting...")


def wrap_functions(queue):
    """
    Creates partials of all API functions with the queue instance
    passed in as first argument.
    """
    for func in api_functions:
        yield functools.wraps(func)(functools.partial(func, queue))


def run(function, *args, **kwargs):
    thread = threading.Thread(target=function, args=args, kwargs=kwargs)
    thread.daemon = True
    thread.start()


def register_backend(name, save, load, populate, expand=None, length=None):
    expand = expand or (lambda queue, item: item)
    length = length or (lambda queue: len(queue))

    backends[name] = Backend(save=save, load=load, populate=populate, expand=expand, length=length)


def find_backend(name):
    return backends.get(name, NOP_BACKEND)
