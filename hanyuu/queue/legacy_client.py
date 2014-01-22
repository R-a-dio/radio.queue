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
    return Song(id=entry.songid)


class Queue(Queue):
    def peek(self, index=0):
        return to_song(self.server.peek(index=index))

    def pop(self):
        return to_song(self.server.pop())

    def append(self, song):
        return self.server.append(from_song(song))

    def append_request(self, song):
        return self.server.append_request(from_song(song))

    def __getitem__(self, point):
        if isinstance(point, slice):
            return [to_song(s) for s in self.server.slice(start=point.start, end=point.stop)]
        elif isinstance(point, int):
            return to_song(self.server.peek(point))

    def __len__(self):
        return self.server.length()

    def __iter__(self):
        return self[0:5]

    def get(self, song):
        for s in self[0:len(self)]:
            if s.id == song.id:
                return QSong(s.id)