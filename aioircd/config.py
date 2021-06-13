__all__ = ['HOST', 'ADDR', 'PORT', 'PASS']

import logging
import os
from socket import gethostname, gethostbyname


HOST = os.getenv('HOST', gethostname())
ADDR = os.getenv('ADDR', gethostbyname(HOST))
PORT = int(os.getenv('PORT', 6667))
PASS = os.getenv('PASS')
TIMEOUT = int(os.getenv('TIMEOUT', 60))
PING_TIMEOUT = int(os.getenv('PING_TIMEOUT', 5))
#DIR = p.realpath(p.abspath(p.expanduser(p.expandvars(p.dirname(__file__)))))
loglevel = os.getenv('LOGLEVEL', 'WARNING')
