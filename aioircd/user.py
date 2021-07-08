import ipaddress
import logging
import trio
import uuid
from typing import Union, List

import aioircd
from aioircd.config import TIMEOUT, PING_TIMEOUT
from aioircd.exceptions import IRCException, Disconnect


logger = logging.getLogger(__name__)
_unsafe_nicks = {
    # RFC
    'anonymous',
    # anope services
    'ChanServ',
    'NickServ',
    'OperServ',
    'MemoServ',
    'HostServ',
    'BotServ',
}
_safenets = [
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('127.0.0.1/8'),
]


class User:
    def __init__(self, stream, nursery):
        servlocal = aioircd.servlocal.get()
        self.stream = stream
        self._nursery = nursery
        self._nick = None
        self._addr = stream.socket.getpeername()
        self.uid = uuid.uuid4()
        self.state = None
        self.state = (PasswordState if servlocal.pwd else ConnectedState)(self)
        self.channels = set()
        self._ping_timer = trio.CancelScope()  # dummy

    def __hash__(self):
        return self.uid.int

    def __str__(self):
        if self.nick:
            return self.nick

        ip, port = self._addr
        if ':' in ip:
            return f'[{ip}]:{port}'
        return f'{ip}:{port}'

    @property
    def nick(self):
        return self._nick

    @nick.setter
    def nick(self, nick):
        servlocal = aioircd.servlocal.get()
        servlocal.users[nick] = servlocal.users.pop(self._nick, self)
        self._nick = nick

    def can_use_nick(self, nick):
        if nick not in _unsafe_nicks:
            return True

        ip = ipaddress.ip_address(self._addr[0])
        return any(ip in net for net in _safenets)

    async def ping_forever(self):
        while True:
            with trio.move_on_after(TIMEOUT - PING_TIMEOUT) as self._ping_timer:
                await trio.sleep_forever()
            await self.stream.send_all(b'PING\r\n')

    async def serve(self):
        buffer = b""
        while type(self.state) is not QuitState:
            self._ping_timer.deadline = trio.current_time() + (TIMEOUT - PING_TIMEOUT)
            with trio.move_on_after(TIMEOUT) as cs:
                try:
                    chunk = await self.stream.receive_some(aioircd.MAXLINELEN)
                except Exception as exc:
                    raise Disconnect("Network failure") from exc
            if cs.cancelled_caught:
                raise Disconnect("Timeout")
            elif not chunk:
                raise Disconnect("End of transmission")

            *lines, buffer = (buffer + chunk).split(b'\r\n')
            if any(len(line) > aioircd.MAXLINELEN - 2 for line in lines + [buffer]):
                raise Disconnect("Payload too long")

            for line in (l for l in lines if l):
                try:
                    cmd, *args = line.decode().split(' ')
                except UnicodeDecodeError as exc:
                    raise Disconnect("Gibberish") from exc

                logger.log(aioircd.IO, "recv from %s: %s", self, line)
                try:
                    await self.state.dispatch(cmd, args)
                except IRCException as exc:
                    logger.warning("Command %s sent by %s failed, code: %s", cmd, self, exc.code)
                    await self.send(exc.args[0])

    async def terminate(self, kick_msg="Kicked by host"):
        logger.info("Terminate connection of %s", self)
        if type(self.state) != QuitState:
            await self.state.dispatch('QUIT', f":{kick_msg}".split(' '))
        with trio.move_on_after(PING_TIMEOUT) as cs:
            await self.stream.send_eof()
        await self.stream.aclose()
        self._nursery.cancel_scope.cancel()

    async def send(self, lines: Union[str, List[str]], log=True):
        if isinstance(lines, str):
            lines = [lines]

        if log:
            for line in lines:
                logger.log(aioircd.IO, "send to %s: %s", self, line)
        await self.stream.send_all(b"".join(f"{line}\r\n".encode() for line in lines))
