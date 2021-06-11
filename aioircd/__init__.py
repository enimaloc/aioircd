__ALL__ = [
    'HOST', 'ADDR', 'PORT', 'PASS',
    'IO', 'SECURITY',
    'logger', 'local_var'
]

import logging
from contextvars import ContextVar
#from os import getenv, path as p
from socket import gethostname, gethostbyname


HOST = os.getenv('HOST', gethostname())
ADDR = os.getenv('ADDR', gethostbyname(HOST))
PORT = int(os.getenv('PORT', 6667))
PASS = os.getenv('PASS')
#DIR = p.realpath(p.abspath(p.expanduser(p.expandvars(p.dirname(__file__)))))
loglevel = os.getenv('LOGLEVEL', 'WARNING')

logger = logging.getLogger(__package__)
IO = logging.INFO - 5
SECURITY = logging.ERROR + 5
logging.addLevelName(IO, 'IO')
logging.addLevelName(SECURITY, 'SECURITY')
logger.setLevel(loglevel)

local_var = ContextVar('local')
