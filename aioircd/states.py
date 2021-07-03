__all__ = [
    'UserState', 'ConnectedState', 'PasswordState', 'RegisteredState',
    'QuitState'
]

import abc
import ipaddress
import logging
import re
import textwrap

import aioircd
from aioircd.channel import Channel
from aioircd.exceptions import *


logger = logging.getLogger(__name__)
nick_re = re.compile(r"[a-zA-Z][a-zA-Z0-9\-_]{0,8}")
chan_re = re.compile(r"#[a-zA-Z0-9\-_]{1,49}")


def command(func):
    """ Denote the function can be triggered by an IRC message """
    func.command = True
    return func


class UserState(metaclass=abc.ABCMeta):
    def __init__(self, user):
        logger.debug("state of user %s changed: %s -> %s", user, user.state, self)
        self.user = user

    def __str__(self):
        return type(self).__name__[:-5]

    async def dispatch(self, cmd, args):
        meth = getattr(self, cmd, None)
        if not meth or not getattr(meth, 'command', False):
            logger.debug("unknown command %s sent by %s", cmd, self.user)
            return

        await meth(args)

    @command
    async def PING(self, args):
        pass  # ignored

    @command
    async def PONG(self, args):
        pass  # ignored

    @command
    async def USER(self, args):
        logger.debug("USER called by %s while in wrong state.", self.user)

    @command
    async def PASS(self, args):
        logger.debug("PASS called by %s while in wrong state.", self.user)

    @command
    async def NICK(self, args):
        logger.debug("NICK called by %s while in wrong state.", self.user)

    @command
    async def JOIN(self, args):
        logger.debug("JOIN called by %s while in wrong state.", self.user)

    @command
    async def PART(self, args):
        logger.debug("PART called by %s while in wrong state.", self.user)

    @command
    async def PRIVMSG(self, args):
        logger.debug("PRIVMSG called by %s while in wrong state.", self.user)

    @command
    async def QUIT(self, args):
        servlocal = aioircd.servlocal.get()
        msg = ' '.join(args) if args else ":Disconnected"
        for chan in self.user.channels:
            chan.users.remove(self.user)
            await chan.send(f":{self.user.nick} QUIT {msg}")
            if not chan.users:
                servlocal.channels.pop(chan.name)
        self.user.channels.clear()
        self.user.state = QuitState(self.user)

        if type(self) not in (PasswordState, ConnectedState):
            servlocal.users.pop(user.nick)


class PasswordState(UserState):
    @command
    async def PASS(self, args):
        if not args:
            raise ErrNeedMoreParams('PASS')
        servlocal = aioircd.servlocal.get()
        if args[0] != servlocal.pwd:
            logger.log(SecurityLevel, "Invalid password for %s", self.user)
            return

        self.user.state = ConnectedState(self.user)


class ConnectedState(UserState):
    """
    The user is just connected, he must register via the NICK command
    first before going on.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_nick = False
        self.has_user = False

    @command
    async def PASS(self, args):
        raise ErrAlreadyRegistred()

    @command
    async def USER(self, args):
        if len(args) < 4:
            raise ErrNeedMoreParams('USER')

        self.has_user = True
        if self.has_user and self.has_nick:
            await self.register()

    @command
    async def NICK(self, args):
        if not args:
            raise ErrNoNicknameGiven()
        servlocal = aioircd.servlocal.get()
        nick = args[0]
        if nick in servlocal.users:
            raise ErrNicknameInUse(nick)
        if not nick_re.match(nick):
            raise ErrErroneusNickname(nick)
        if not user.can_use_nick(nick):
            logger.log(aioircd.SECURITY, '%s tried to use nick %s', user, nick)
            raise ErrErroneusNickname(nick)

        self.user.nick = nick
        self.has_nick = True
        if self.has_user and self.has_nick:
            await self.register()

    async def register(self):
        host = aioircd.servlocal.get().host
        self.user.state = RegisteredState(self.user)
        nick = self.user.nick
        await self.user.send([
            f":{host} 001 {nick} :Welcome to the Internet Relay Network {nick}",
            f":{host} 002 {nick} :Your host is {host}",
            f":{host} 003 {nick} :The server was created at some point",
            f":{host} 004 {nick} :aioircd {aioircd.__version__}  ",
            #                             available user modes ^
            #                           available channel modes ^
        ])


class RegisteredState(UserState):
    """
    The user sent the NICK command, he is fully registered to the server
    and may use any command.
    """

    @command
    async def PASS(self, args):
        raise ErrAlreadyRegistred()

    @command
    async def USER(self, args):
        raise ErrAlreadyRegistred()

    @command
    async def NICK(self, args):
        servlocal = aioircd.servlocal.get()
        if not args:
            raise ErrNoNicknameGiven()
        nick = args[0]
        if nick in servlocal.users:
            raise ErrNicknameInUse(nick)
        if not nick_re.match(nick):
            raise ErrErroneusNickname(nick)
        self.user.nick = nick

    @command
    async def JOIN(self, args):
        servlocal = aioircd.servlocal.get()
        if not args:
            raise ErrNeedMoreParams('JOIN')

        for channel in args:
            if not chan_re.match(channel):
                await self.user.send(ErrNoSuchChannel.format(channel))
                continue

            # Find or create the channel, add the user in it
            chan = servlocal.channels.get(channel)
            if not chan:
                chan = Channel(channel)
                servlocal.channels[chan.name] = chan
            chan.users.add(self.user)
            self.user.channels.add(chan)

            # Send JOIN response to all
            await chan.send(f":{self.user.nick} JOIN {channel}")

            # Send NAMES list to joiner
            nicks = " ".join(sorted(user.nick for user in chan.users))
            prefix = f":{servlocal.host} 353 {self.user.nick} = {channel} :"
            maxwidth = 1024 - len(prefix) - 2  # -2 is \r\n
            for line in textwrap.wrap(nicks, width=maxwidth):
                await self.user.send(prefix + line)
            await self.user.send(f":{servlocal.host} 366 {self.user.nick} {channel} :End of /NAMES list.")

    @command
    async def PART(self, args):
        servlocal = aioircd.servlocal.get()
        if not args:
            raise ErrNeedMoreParams('PART')

        msg = ' '.join(args[1:]) or ":Left"

        for channel in args[0].split(','):
            chan = servlocal.channels.get(channel)
            if not chan:
                await self.user.send(ErrNoSuchChannel.format(channel))
                continue

            if self.user not in chan:
                await self.users.send(ErrNotOnChannel.format(channel))
                continue

            self.user.channels.remove(chan)
            chan.remove(self.user)
            if not chan.users:
                servlocal.channels.pop(chan.name)

            await chan.send(f":{self.user.nick} PART {channel} {msg}")

    @command
    async def PRIVMSG(self, args):
        if not args or args[0] == "":
            raise ErrNoRecipient('PRIVMSG')

        servlocal = aioircd.servlocal.get()
        dest = args[0]
        msg = " ".join(args[1:])
        if not msg or not msg.startswith(':') or len(msg) < 2:
            raise ErrNoTextToSend()

        if dest.startswith('#'):
            # Relai channel message to all
            chann = servlocal.channels.get(dest)
            if not chann:
                raise ErrNoSuchChannel(dest)
            await chann.send(f":{self.user.nick} PRIVMSG {dest} {msg}", skipusers={self.user})
        else:
            # Relai private message to user
            receiver = self.user.local.users.get(dest)
            if not receiver:
                raise ErrErroneusNickname(dest)
            await receiver.send(f":{self.user.nick} PRIVMSG {dest} {msg}")

class QuitState(UserState):
    """ The user sent the QUIT command, no more message should be processed """

    @command
    def QUIT(self, args):
        logger.debug("QUIT called by %s while in wrong state.", self.user)
