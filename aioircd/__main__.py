import os
import logging
import aioircd


# Color the [LEVEL] part of messages, need new terminal on Windows
# https://github.com/odoo/odoo/blob/13.0/odoo/netsvc.py#L57-L100
class ColoredFormatter(logging.Formatter):
    colors = {
        logging.DEBUG: (34, 49),
        aioircd.IO: (32, 49),
        logging.INFO: (37, 49),
        logging.WARNING: (33, 49),
        logging.ERROR: (31, 49),
        logging.SECURITY: (31, 49),
        logging.CRITICAL: (37, 41),
    }
    def format(self, record):
        fg, bg = type(self).colors.get(record.levelno, (32, 49))
        record.levelname = f"\033[1;{fg}m\033[1;{bg}m{record.levelname}\033[0m"
        return super().format(record)

def setup():

def main():
    stderr = logging.StreamHandler()
    stderr.formatter = (
        ColoredFormatter("%(asctime)s [%(levelname)s] <%(funcName)s> %(message)s")
        if hasattr(stderr, 'fileno') and os.isatty(stderr.fileno()) else
        logging.Formatter("[%(levelname)s] <%(funcName)s> %(message)s")
    )

    try:
        ...
    except Exception:
        logging.critical("Dead", exc_info=True)
