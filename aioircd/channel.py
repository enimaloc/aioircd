import logging
import trio
from functools import partial
from typing import Union, List

import aioircd


logger = logging.getLogger(__name__)


class Channel:
    def __init__(self, name):
        self._name = name
        self.users = set()

    def __str__(self):
        return self._name

    @property
    def name(self):
        return self._name

    async def send(self, lines: Union[str, List[str]], skipusers=[]):
        if isinstance(lines, str):
            lines = [lines]

        async with trio.open_nursery() as self._nursery:
            for line in lines:
                logging.log(aioircd.IO, "send to %s: %s", self, line)
            for user in self.users:
                if user in skipusers:
                    continue
                self._nursery.start_soon(partial(user.send, lines, log=False))
