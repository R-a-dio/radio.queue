from __future__ import absolute_import, unicode_literals
import os

import mutagen

from .server import create_entry, register_backend


def populate(queue):
    for filepath in queue.walker:
        try:
            meta = mutagen.File(filepath, easy=True)
        except:
            continue

        if not meta:
            continue

        artist = ", ".join(meta.get('artist', []))
        title = ", ".join(meta.get('title', []))

        if artist:
            metadata = "{artist:s} - {title:s}"
            metadata = metadata.format(artist=artist, title=title)
        else:
            metadata = title

        entry = create_entry(
            songid=queue.amount_of_items,
            length=int(meta.info.length),
            metadata=metadata,
            filename=filepath,
            request=False,
        )

        with queue.lock:
            queue.append(entry)
            queue.amount_of_items += 1

            if len(queue) > 5:
                break
    else:
        # We ran it empty, call ourself again
        if queue.amount_of_items > 0:
            load(queue)
            populate(queue)


def save(queue):
    pass


def load(queue):
    directory = queue.config['music_root']

    queue.walker = walk(directory)
    queue.amount_of_items = 0


def expand(queue, entry):
    return entry


register_backend("directory", save, load, populate, expand)


def walk(directory):
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            yield os.path.join(root, filename)