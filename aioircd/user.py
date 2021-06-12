import aioircd
import ipaddress
import uuid
import trio

from aioircd.states import *
from aioircd.exceptions import IRCException, Disconnect, Kick

class User:
    def __init__(self, stream):
        servlocal = aioircd.servlocal.get()
        self.stream = stream
        self._nick = None
        self.uid = uuid.uuid4()
        self.state = None
        self.state = (PasswordState if servlocal.pwd else ConnectedState)(self)
        self.channels = set()
        self._ping_timer = trio.CancelScope()  # dummy

    def __hash__(self):
        return self.uid.int

    @property
    def nick(self):
        return self._nick

    @nick.setter
    def nick(self, nick):
        local = aioircd.local_var.get()
        local.users[nick] = local.users.pop(self._nick, self)
        self._nick = nick

    def __str__(self):
        if self.nick:
            return self.nick

        ip, port, *_ = self.stream.socket.get_extra_info('peername')
        if isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address):
            return f'[{ip}]:{port}'
        return f'{ip}:{port}'

    async def ping_forever(self):
        while True:
            with trio.move_on_after(5) as self._ping_timer:
                await trio.sleep_forever()
            await self.stream.send_all(b'PING\r\n')

    async def serve(self):
        buffer = b""
        while type(self.state) is not QuitState:
            self._ping_timer.deadline = \
                trio.current_time() + (TIMEOUT - PING_TIMEOUT)
            with trio.move_on_after(TIMEOUT) as cs:
                try:
                    chunk = await self.stream.receive_some(1024)
                except Exception as exc:
                    raise Disconnect("Network failure") from exc
            if cs.cancelled_caught:
                raise Disconnect("Timeout")
            elif not chunk:
                buffer = b"QUIT :End of transmission"
            else:
                buffer += chunk

            *lines, buffer = buffer.split(b'\r\n')
            if any(len(line) > 1022 for line in lines + [buffer]):
                raise Disconnect("Buffer overflow", exploit=True) from (
                    MemoryError("Message exceed 1024 bytes"))

            for line in [l for l in lines if l]:
                try:
                    cmd, *args = line.decode().split(' ')
                except UnicodeDecodeError as exc:
                    raise Disconnect("Gibberish", exploit=True) from exc

                try:
                    self.state.dispatch(cmd, args)
                except IRCException:
                    logger.warning("Command %s sent by %s failed, code: %s",
                        cmd, self, exc.code)
                    await self.user.send(exc.args[0])

    async def terminate(self, kick_msg="Kicked by host"):
        logger.info("terminate connection of %s", self)
        if hasattr(self, '_nursery'):
            self._nursery.cancel_scope.cancel()

        if type(self.state) != StateQuit:
            await self.state.dispatch(f"QUIT :{kick_msg}")

        with trio.move_on_after(PING_TIMEOUT) as cs:
            await self.stream.send_eof()
        await self.stream.aclose()
