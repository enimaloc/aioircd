__all__ = [
    'UserState', 'ConnectedState', 'PasswordState', 'RegisteredState',
    'QuitState'
]

import abc
import inspect
import ipaddress
import logging
import re
import textwrap
import trio

import aioircd
from aioircd.channel import Channel
from aioircd.exceptions import *


logger = logging.getLogger(__name__)
nick_re = re.compile(r"[a-zA-Z][a-zA-Z0-9\-_]{0,15}")
chan_re = re.compile(r"&[a-zA-Z0-9\-_]{1,49}")


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

    async def dispatch(self, cmd, *params):
        meth = getattr(self, cmd, None)
        if not meth or not getattr(meth, 'command', False):
            logger.debug("unknown command %s sent by %s", cmd, self.user)
            return

        meth_params_cnt = len(inspect.signature(meth).parameters.values())

        if len(params) < meth_params_cnt:
            raise ErrNeedMoreParams(cmd)
        if len(params) > meth_params_cnt:
            logger.warning(
                '%s only has %s parameters but %s sent %s: %s. List truncated.',
                cmd, meth_params_cnt, self.user, len(params), params
            )
            params = params[:meth_params_cnt]

        await meth(*params)

    @command
    async def PING(self, args):
        pass  # ignored

    @command
    async def PONG(self, args):
        pass  # ignored

    @command
    async def USER(self, username, _zero, _star, realname):
        logger.debug("USER called by %s while in wrong state.", self.user)

    @command
    async def PASS(self, password, *):
        logger.debug("PASS called by %s while in wrong state.", self.user)

    @command
    async def NICK(self, nickname):
        logger.debug("NICK called by %s while in wrong state.", self.user)

    @command
    async def JOIN(self, channels):
        logger.debug("JOIN called by %s while in wrong state.", self.user)

    @command
    async def PART(self, channels, reason=""):
        logger.debug("PART called by %s while in wrong state.", self.user)

    @command
    async def NAMES(self, channel):
        logger.debug("NAMES called by %s while in wrong state.", self.user)

    @command
    async def LIST(self):
        logger.debug("LIST called by %s while in wrong state.", self.user)

    @command
    async def PRIVMSG(self, args):
        logger.debug("PRIVMSG called by %s while in wrong state.", self.user)

    @command
    async def QUIT(self, reason="", *, kick=False):
        servlocal = aioircd.servlocal.get()
        if not kick:
            reason = 'Quit: ' + reason
        for chan in self.user.channels:
            chan.users.remove(self.user)
            await chan.send(f":{self.user.nick} QUIT :{reason}")
            if not chan.users:
                servlocal.channels.pop(chan.name)
        self.user.channels.clear()
        self.user.state = QuitState(self.user)

        if type(self) not in (PasswordState, ConnectedState):
            servlocal.users.pop(user.nick)


class PasswordState(UserState):
    @command
    async def PASS(self, password):
        if not args:
            raise ErrNeedMoreParams('PASS')
        servlocal = aioircd.servlocal.get()
        if args[0] != servlocal.pwd:
            logger.log(SecurityLevel, "Invalid password for %s", self.user)
            raise ErrPasswdMismatch()

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
    async def PASS(self, password):
        raise ErrAlreadyRegistred()

    @command
    async def USER(self, username, _zero, _star, realname):
        self.has_user = True
        if self.has_user and self.has_nick:
            await self.register()

    @command
    async def NICK(self, nickname):
        servlocal = aioircd.servlocal.get()
        if nickname in servlocal.users:
            raise ErrNicknameInUse(nickname)
        if not nick_re.match(nickname):
            raise ErrErroneusNickname(nickname)
        if not user.can_use_nick(nickname):
            logger.log(aioircd.SECURITY, '%s tried to use nick %s', user, nickname)
            raise ErrErroneusNickname(nickname)

        self.user.nick = nickname
        self.has_nick = True
        if self.has_user and self.has_nick:
            await self.register()

    async def register(self):
        servlocal = aioircd.servlocal.get()
        self.user.state = RegisteredState(self.user)

        h = host = servlocal.host
        n = nick =self.user.nick
        version=aioircd.__version__

        # RPL_MYINFO (004), advertise availables modes (none)
        usermodes=""
        chanmodes=""

        # RPL_ISUPPORT (005), advertise server capabilities (not much)
        cap1=('AWAYLEN=0 CASEMAPPING=ascii CHANLIMIT=#:0,&: CHANMODES= '
              'CHANNELLEN=50 CHANTYPES=& ELIST=')
        cap2=('HOSTLEN=63 KICKLEN=0 MAXLIST= MAXTARGETS=12MODES=0 '
              'NICKLEN=15 STATUSMSG= TOPICLEN=0 USERLEN=1')

        await self.user.send(textwrap.dedent(f"""\
            :{h} 001 {n} :Welcome to the Internet Relay Network {nick}
            :{h} 002 {n} :Your host is {host}, running version {version}
            :{h} 003 {n} :The server was created someday
            :{h} 004 {n} aioircd {version} {usermodes} {chanmodes}
            :{h} 005 {n} {cap1} :are supported by this server
            :{h} 005 {n} {cap2} :are supported by this server
            :{h} 422 {n} :MOTD File is missing""").split('\n'))

class RegisteredState(UserState):
    """
    The user sent the NICK command, he is fully registered to the server
    and may use any command.
    """

    @command
    async def PASS(self, password):
        raise ErrAlreadyRegistred()

    @command
    async def USER(self, username, _zero, _star, realname):
        raise ErrAlreadyRegistred()

    @command
    async def NICK(self, nickname):
        servlocal = aioircd.servlocal.get()

        if nickname in servlocal.users:
            raise ErrNicknameInUse(nickname)
        if not nick_re.match(nickname):
            raise ErrErroneusNickname(nickname)

        old_nick = self.user.nick
        async with trio.open_nursery() as nursery:
            for chan in self.user.channels:
                nursery.start_soon(chan.send, f":{old_nick} NICK {nickname}")

        self.user.nick = nickname

    @command
    async def JOIN(self, channels):
        servlocal = aioircd.servlocal.get()

        for channel in channels.split(','):
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
            await self.NAMES(channel)

    @command
    async def PART(self, channels, reason=None):
        servlocal = aioircd.servlocal.get()

        for channel in channels.split(','):
            chan = servlocal.channels.get(channel)
            if not chan:
                await self.user.send(ErrNoSuchChannel.format(channel))
                continue

            if self.user not in chan:
                await self.user.send(ErrNotOnChannel.format(channel))
                continue

            self.user.channels.remove(chan)
            chan.remove(self.user)
            if not chan.users:
                servlocal.channels.pop(chan.name)

            if reason:
                await chan.send(f":{self.user.nick} PART {channel} :{reason}")
            else:
                await chan.send(f":{self.user.nick} PART {channel}")

    @command
    async def NAMES(self, channel):
        servlocal = aioircd.servlocal.get()
        chan = servlocal.channels.get(channel)
        host = servlocal.host
        nick = self.user.nick

        if chan:
            await self.user.send([
                f":{host} 353 {nick} = {chan} :{some_users}"
                # merged all users in a str and split it by MAXLINELEN chunks
                for some_users in textwrap.wrap(
                    ' '.join(sorted(user.nick for user in chan.users)),
                    width=aioircd.MAXLINELEN - len(host) - len(nick) - len(channel) - 13
                )
            ])

        await self.user.send(f":{host} 366 {nick} {chan} :End of /NAMES list.")
            
    @command
    async def LIST(self):
        servlocal = aioircd.servlocal.get()
        host = servlocal.host
        nick = self.user.nick

        await self.user.send([
            f":{host} 321 {nick} Channel :Users Name",
            *[
                f":{host} 322 {nick} {chan} {len(chan.users)} :"
                for chan in servlocal.channels.values()
            ],
            f":{host} 323 {nick} :End of /LIST"
        ])

    @command
    async def PRIVMSG(self, targets, text):
        servlocal = aioircd.servlocal.get()

        for target in targets.split(','):
            chan_or_user = (
                servlocal.channels.get(target)
                if target.startswith('&') else
                servlocal.users.get(target)
            )

            if not chan_or_user:
                await self.user.send(ErrNoSuchNick.format(target))
                continue

            await chan_or_user.send(
                f":{self.user.nick} PRIVMSG {target} {text}",
                skipusers={self.user}
            )

class QuitState(UserState):
    """ The user sent the QUIT command, no more message should be processed """

    @command
    def QUIT(self, args):
        logger.debug("QUIT called by %s while in wrong state.", self.user)
