import aioircd
import logging
import trio

logger = logging.getLogger(__name__)

class Channel:
    count = 0

    def __init__(self, name):
        self.local = aioircd.local_var.get()
        self._name = name
        self.users = set()
        self.gid = type(self).count
        type(self).count += 1

    def __str__(self):
        return self._name

    def __hash__(self):
        return hash(self._name)

    @property
    def name(self):
        return self._name

    async def send(self, lines: , skipusers=[]):
        if isinstance(lines: , str):
            lines = [lines]

        async with trio.open_nursery() as self._nursery:
            for line in lines:
                logging.log(aioircd.IO, 'send to %s: %s', self, line)
            for user in self.users:
                if user in skipusers:
                    continue
                self._nursery.start_soon(user.send(lines, log=False))
