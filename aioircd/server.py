import aioircd
from contextvars import ContextVar
from dataclasses import dataclass, field

class Server:
    def __init__(self, host, port, pwd):
        self.host = host
        self.port = port
        self.local = ServerLocal(pwd)



    async def start(self):
        aioircd.local_var.set(self.local)
        ...

    def handle(self, reader, writer):
        ...

    async def _handle(self, reader, writer):
        ...

    async def shutdown(self):
        ...

@dataclass(eq=False)
class ServerLocal:
    """ Storage shared among all server's entities """
    pwd: str
    users: field(default_factory=dict)
    channels: field(default_factory=dict)
