from __future__ import absolute_import
import Queue
import os.path
import time
import random

import MySQLdb as mysql
import MySQLdb.cursors

from .server import create_entry, register_backend


RANDOM_SELECT_ADVANCED = """
SELECT temp.id, temp.path, temp.len, temp.meta FROM (
    (SELECT tracks.id, tracks.path, esong.len, esong.meta FROM tracks
        JOIN esong ON tracks.hash = esong.hash WHERE usable=1 ORDER BY
        (UNIX_TIMESTAMP(lastplayed) + 1)*(UNIX_TIMESTAMP(lastrequested) + 1)
        ASC LIMIT 100)
    UNION ALL
    (SELECT tracks.id, tracks.path, esong.len, esong.meta FROM tracks
        JOIN esong ON tracks.hash = esong.hash WHERE usable=1 ORDER BY
        LEAST(lastplayed, lastrequested)
        ASC LIMIT 100)
) AS temp GROUP BY temp.id HAVING count(*) >= 2;
"""

RANDOM_SELECT = """
SELECT tracks.id, tracks.path,
esong.len, esong.meta FROM
tracks JOIN esong ON tracks.hash = esong.hash
WHERE usable=1 AND tracks.id NOT IN (%s)
ORDER BY LEAST(lastplayed, lastrequested) ASC
LIMIT 100;
"""

LR_UPDATE = """
UPDATE tracks SET lastrequested=NOW() WHERE id=%s;
"""

LOAD_QUEUE = """
SELECT trackid, meta, length, type FROM `queue` ORDER BY `id` ASC;
"""

LOAD_PATH = """
SELECT path FROM `tracks` WHERE `id`=%s;
"""

DELETE_QUEUE = """
DELETE FROM `queue`;
"""

INSERT_QUEUE = """
INSERT INTO queue (trackid, time, ip, type, meta, length, id)
VALUES (%s, from_unixtime(%s), NULL, %s, %s, %s, %s);
"""

EXPAND = """
SELECT tracks.path, esong.len, esong.meta FROM
tracks JOIN esong ON tracks.hash = esong.hash
WHERE tracks.id=%s;
"""

def cursor_factory(**factory_options):
    def cursor(**options):
        options.update(factory_options)
        return Cursor(**options)
    return cursor

def populate(queue):
    """
    Populates any missing entries in the queue.
    """
    queue.last_pop = time.time()

    with queue.lock:
        randoms = sum(not bool(entry.request) for entry in queue)
        reqs = sum(bool(entry.request) for entry in queue)
        threshold = (10 - min(reqs, 10)) / 2

        if randoms >= threshold:
            return

        # ids = [entry.songid for entry in queue]
        # ids.append(0) # ensure that there is an entry in the list

        with queue.cursor() as cur:
            cur.execute(RANDOM_SELECT_ADVANCED)
            # cur.execute(RANDOM_SELECT % ','.join(["%s"] * len(ids)), ids)

            all = list(cur.fetchall())
            for i in range(threshold - randoms): # add up to threshold entries
                trackid, path, length, meta = all.pop(random.randint(0, len(all)-1))
                cur.execute(LR_UPDATE, (trackid,))

                entry = create_entry(
                    songid=trackid,
                    length=length,
                    metadata=meta,
                    filename=os.path.join(queue.config['music_root'], path),
                    request=False,
                )

                queue.append(entry)

def save(queue):
    """
    Saves the queue.
    """
    now = time.time()
    time_acc = queue.last_pop

    with queue.cursor() as cur:
        cur.execute(DELETE_QUEUE)
        with queue.lock:
            for i, entry in enumerate(queue):
                time_acc = time_acc + entry.length
                cur.execute(INSERT_QUEUE, (
                    entry.songid, int(time_acc),
                    '1' if entry.request else '0', entry.metadata,
                    entry.length, i+1))

def load(queue):
    """
    Populates `queue` with a previous save.
    """
    queue.cursor = cursor_factory(**queue.config.get("mysql", {}))
    queue.last_pop = time.time()

    with queue.cursor() as cur:
        cur.execute(LOAD_QUEUE)
        for trackid, meta, length, type in cur:

            with queue.cursor() as cur2:
                cur2.execute(LOAD_PATH, (trackid,))
                if cur2.rowcount == 1:
                    path, = cur2.fetchone()

                    filename = os.path.join(queue.config.get('music_root', ''), path)
                else:
                    # did not find the song in DB; skip this entry
                    # logging?
                    continue

            entry = create_entry(
                songid=trackid,
                metadata=meta,
                length=length,
                request= type == 1,
                filename=filename,
            )

            with queue.lock:
                queue.append(entry)


def expand(queue, entry):
    if not entry.songid:
        return entry

    with queue.cursor() as cur:
        cur.execute(EXPAND, (entry.songid,))

        for path, length, meta in cur:
            if not entry.filename:
                entry.filename = os.path.join(queue.config.get('music_root', ''), path)
            if not entry.length:
                entry.length = length
            if not entry.metadata:
                entry.metadata = meta

    return entry


def length(queue):
    with queue.cursor() as cur:
        cur.execute(LOAD_QUEUE)
        return cur.rowcount

register_backend("mysql", save, load, populate, expand, length)


class Cursor(object):
    """
    Establishes a connection to the database and returns an open cursor.


    ```python
    # Use as context manager
    with Cursor() as cur:
    cur.execute(query)
    ```
    """
    _cache = Queue.Queue(maxsize=5)

    def __init__(self, cursor_type=mysql.cursors.Cursor, **options):
        super(Cursor, self).__init__()

        try:
            conn = self._cache.get_nowait()
        except Queue.Empty:
            conn = mysql.connect(**options)
        else:
            # Ping the connection before using it from the cache.
            conn.ping(True)

        self.conn = conn
        self.conn.autocommit(False)
        self.cursor_type = cursor_type

    @classmethod
    def clear_cache(cls):
        cls._cache = Queue.Queue(maxsize=5)

    def __enter__(self):
        self.cursor = self.conn.cursor(self.cursor_type)
        return self.cursor

    def __exit__(self, extype, exvalue, traceback):
        # if we had a MySQL related error we try to rollback the cursor.
        if extype is mysql.MySQLError:
            self.cursor.rollback()

        self.cursor.close()
        self.conn.commit()

        # Put it back on the queue
        try:
            self._cache.put_nowait(self.conn)
        except Queue.Full:
            self.conn.close()
