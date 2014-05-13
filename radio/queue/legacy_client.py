from __future__ import absolute_import

from .client import Queue
from .server import Entry


def from_song(song):
    return Entry(
        songid=song.id,
        filename=song.filename,
        metadata=song.metadata,
        length=song.length,
        request=False,
    )

def to_song(entry):
    return QSong(id=entry.songid, type=1 if entry.request else 0, time=entry.estimate)


class Queue(Queue):
    def peek(self, index=0):
        return to_song(super(Queue, self).peek(index=index))

    def pop(self):
        return to_song(super(Queue, self).pop())

    def append(self, song):
        return super(Queue, self).append(from_song(song))

    def append_request(self, song):
        return super(Queue, self).append_request(from_song(song))

    def __getitem__(self, point):
        if isinstance(point, slice):
            return [to_song(s) for s in super(Queue, self).__getitem__(point)]
        elif isinstance(point, int):
            return to_song(super(Queue, self).peek(point))

    def __len__(self):
        return self.server.length()

    def __iter__(self):
        return iter(self[0:5])

    def iter(self, limit=None):
        if not limit:
            limit = len(self)
        return self[0:limit]

    def clear_pops(self):
	pass # yep it does nothing

    def get(self, song):
        for s in self[0:len(self)]:
            if s.songid == song.id:
                return QSong(id=s.id, type=1 if s.request else 0, time=s.estimate)
        raise QueueError()
