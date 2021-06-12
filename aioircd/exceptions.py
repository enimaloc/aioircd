class Disconnect(Exception):
    def __init__(self, *, exploit=False):
        self.exploit = exploit

class IRCException(Exception):
    """
    Abstract IRC exception

    They are excepted by dispatch() and forwarded to the user.
    """
    def __init__(self, *args):
        super().__init__(type(self).format(*args))

    @classmethod
    def format(cls, *args):
        return ":{host} {code} {error}".format(
            host=HOST,
            code=cls.code,
            error=cls.msg % args,
        )

class ErrNoSuchChannel(IRCException):
    msg = "%s :No such channel"
    code = "403"

class ErrNoRecipient(IRCException):
    msg = ":No recipient given (%s)"
    code = "411"

class ErrNoTextToSend(IRCException):
    msg = ":No text to send"
    code = "412"

class ErrUnknownCommand(IRCException):
    msg = "%s :Unknown command"
    code = "421"

class ErrNoNicknameGiven(IRCException):
    msg = ":No nickname given"
    code = "431"

class ErrErroneusNickname(IRCException):
    msg = "%s :Erroneous nickname"
    code = "432"

class ErrNicknameInUse(IRCException):
    msg = "%s :Nickname is already in use"
    code = "433"

class ErrNoLogin(IRCException):
    msg = ":User not logged in"
    code = "444"

class ErrNeedMoreParams(IRCException):
    msg = "%s :Not enough parameters"
    code = "461"

class ErrAlreadyRegistred(IRCException):
    msg = ":Unauthorized command (already registered)"
    code = "462"
