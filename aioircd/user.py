import aioircd
import ipaddress

class User:
    count = 0

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.local = aioircd.local_var.get()
        self._nick = None
        self.state = None
        self.state = StatePassword(self) if local.pwd else StateConnected(self)
        self.channels = set()
        self.uid = type(self).count
        type(self).count += 1

    def __hash__(self):
        return self.uid

    @property
    def nick(self):
        return self._nick

    @nick.setter
    def nick(self, nick):
        self.local.users[nick] = self.local.users.pop(self._nick, self)
        self._nick = nick

    @property
    def addr(self):
        ip = ipaddress self.writer.get_extra_info('peername')[0]
        return

    def __str__(self):
        return self.nick or self.addr

    async def read_lines(self):
        """
        Read messages until (i) the user send a QUIT command or (ii) the
        user close his side of the connection (FIN sent) or (iii) the
        connection is reset.
        """
        buffer = b""
        graceful_close = True
        while type(self.state) != StateQuit:
            chunk = b""
            self._read_task = asyncio.create_task(self.reader.read(1024))
            self.reschedule_ping()
            try:
                chunk = await asyncio.wait_for(self._read_task, TIMEOUT)
            except asyncio.CancelledError:
                buffer = b"QUIT :Kicked\r\n"
                graceful_close = False
            except asyncio.TimeoutError:
                buffer = b"QUIT :Ping timeout\r\n"
                graceful_close = False
            except ConnectionResetError:
                buffer = b"QUIT :Connection reset by peer\r\n"
                graceful_close = False
            else:
                if not chunk:
                    buffer = b"QUIT :EOF Received\r\n"


            # imagine two messages of 768 bytes are sent together, read(1024)
            # only read the first one and the 256 first bytes of the second,
            # the first ends up in lines, the second in buffer. Next call to
            # read(1024) will complete the second message.
            buffer += chunk
            *lines, buffer = buffer.split(b'\r\n')
            if any(len(line) > 1022 for line in lines + [buffer]):
                # one IRC message cannot exceed 1024 bytes (\r\n included)
                raise MemoryError("Message exceed 1024 bytes")

            for line in lines:
                try:
                    line = line.decode('utf-8')
                except UnicodeDecodeError:
                    line = line.decode('latin-1')
                yield line

        if graceful_close:
            self.writer.write_eof()
            await self.writer.drain()


    async def serve(self):
        """ Listen for new messages and process them """
        async for line in self.read_lines():
            logger_io.log(IOLevel, "<%s %s", self, line)
            cmd, *args = line.split()
            func = getattr(self.state, cmd, None)
            if getattr(func, 'command', False):
                try:
                    await func(args)
                except IRCException as exc:
                    logger.warning("%s sent an invalid command.", self)
                    await self.send(exc.args[0])
            else:
                logger.warning("%s sent an unknown command: %s", self, cmd)

    async def send(self, msg: str, log=True):
        """ Send a message to the user """
        if self.writer.is_closing():
            return
        for line in msg.splitlines():
            if log:
                logger_io.log(IOLevel, ">%s %s", self, line)
            self.writer.write(f"{line}\r\n".encode())
        await self.writer.drain()

    async def terminate(self):
        asyncio.get_running_loop().call_later(PING_TIMEOUT, self._read_task.cancel)
        self.writer.write_eof()
        await self.writer.drain()
