import abc
import aioircd
from aioircd.exceptions import *

__all__ = [
    'UserState', 'ConnectedState', 'PasswordState', 'RegisteredState',
    'QuitState'
]

def command(func):
    """ Denote the function can be triggered by an IRC message """
    func.command = True
    return func


class UserState(metaclass=abc.ABCMeta):
    def __init__(self, user):
        logger.debug("state of user %s changed: %s -> %s", user, user.state, self)
        self.user = user

    def __str__(self):
        return type(self).__name__[:5]

    async def dispatch(self, cmd, args):
        meth = getattr(self, cmd, None)
        if not meth or not getattr(meth, 'command', False):
            logger.debug("unknown command %s sent by %s", cmd, self.user)
            return

        await meth(cmd, args)


    @command
    async def PING(self, args):
        pass  # ignored

    @command
    async def PONG(self, args):
        pass  # ignored

    @command
    async def USER(self, args):
        logger.debug("user called by %s while in wrong state.", self.user)

    @command
    async def PASS(self, args):
        logger.debug("pass called by %s while in wrong state.", self.user)

    @command
    async def NICK(self, args):
        logger.debug("nick called by %s while in wrong state.", self.user)

    @command
    async def JOIN(self, args):
        logger.debug("join called by %s while in wrong state.", self.user)

    @command
    async def PRIVMSG(self, args):
        logger.debug("privmsg called by %s while in wrong state.", self.user)

    @command
    async def QUIT(self, args):
        msg = " ".join(args) if args else ":Disconnected"
        for channel in self.user.channels:
            channel.users.remove(self.user)
            await channel.send(f":{self.user.nick} QUIT {msg}")
            if not channel.users:
                self.user.local.channels.pop(channel.name)
        self.user.channels.clear()
        self.user.state = QuitState(self.user)


class PasswordState(UserState):
    @command
    async def PASS(self, args):
        if not args:
            raise ErrNeedMoreParams('PASS')
        if args[0] != self.user.local.pwd:
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
        nick = args[0]
        if nick in self.user.local.users:
            raise ErrNicknameInUse(nick)
        if not nick_re.match(nick):
            raise ErrErroneusNickname(nick)
        if nick in unsafe_nicks and self.user.ip not in safe_addrs:
            raise ErrErroneusNickname(nick)

        self.user.nick = nick
        self.has_nick = True
        if self.has_user and self.has_nick:
            await self.register()

    async def register(self):
        self.user.state = RegisteredState(self.user)
        nick = self.user.nick
        await self.user.send(textwrap.dedent(f"""\
            :{HOST} 001 {nick} :Welcome to the Internet Relay Network {nick}@!
            :{HOST} 002 {nick} :Your host is {HOST}
            :{HOST} 003 {nick} :The server was created at some point
            :{HOST} 004 {nick} :aioircd {aioircd.__version__}  """))
            #                                                 ^ available channel modes
            #                                                ^ available user modes


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
        if not args:
            raise ErrNoNicknameGiven()
        nick = args[0]
        if nick in self.user.local.users:
            raise ErrNicknameInUse(nick)
        if not nick_re.match(nick):
            raise ErrErroneusNickname(nick)
        self.user.nick = nick

    @command
    async def JOIN(self, args):
        if not args:
            raise ErrNeedMoreParams("JOIN")
        for channel in args:
            if not chann_re.match(channel):
                await self.user.send(ErrNoSuchChannel.format(channel))

            # Find or create the channel, add the user in it
            chann = self.user.local.channels.get(channel)
            if not chann:
                chann = Channel(channel, self.user.local)
                self.user.local.channels[chann.name] = chann
            chann.users.add(self.user)
            self.user.channels.add(chann)

            # Send JOIN response to all
            await chann.send(f":{self.user.nick} JOIN {channel}")

            # Send NAMES list to joiner
            nicks = " ".join(sorted(user.nick for user in chann.users))
            prefix = f":{HOST} 353 {self.user.nick} = {channel} :"
            maxwidth = 1024 - len(prefix) - 2  # -2 is \r\n
            for line in textwrap.wrap(nicks, width=maxwidth):
                await self.user.send(prefix + line)
            await self.user.send(f":{HOST} 366 {self.user.nick} {channel} :End of /NAMES list.")

    @command
    async def PRIVMSG(self, args):
        if not args or args[0] == "":
            raise ErrNoRecipient("PRIVMSG")

        dest = args[0]
        msg = " ".join(args[1:])
        if not msg or not msg.startswith(":") or len(msg) < 2:
            raise ErrNoTextToSend()

        if dest.startswith("#"):
            # Relai channel message to all
            chann = self.user.local.channels.get(dest)
            if not chann:
                raise ErrNoSuchChannel(dest)
            await chann.send(f":{self.user.nick} PRIVMSG {dest} {msg}", skip={self.user})
        else:
            # Relai private message to user
            receiver = self.user.local.users.get(dest)
            if not receiver:
                raise ErrErroneusNickname(dest)
            await receiver.send(f":{self.user.nick} PRIVMSG {dest} {msg}")


class QuitState(UserState):
    """ The user sent the QUIT command, no more message should be processed """


