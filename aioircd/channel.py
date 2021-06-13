import logging

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
        return self.gid

    @property
    def name(self):
        return self._name

    async def send(self, msg, skipusers=()):
        ...
