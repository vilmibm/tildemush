import os
import logging

from .models import Log

class PGHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.env = os.environ.get('TILDEMUSH_ENV', 'live')

    def emit(self, record):
        # there may end up being a bit of a skew between when a call to log is issued and when the
        # created_at is set for a Log record. For the sake of expediency i'm ok with that, but if it
        # ends up being an issue this should parse and use record.created
        Log.create(
            env=self.env,
            raw=record.getMessage(),
            level=record.levelname)


def get_logger(debug=False):
    if debug:
        logging.basicConfig(level=logging.INFO)

    logger = logging.getLogger('tmserver')

    if not debug:
        logger.addHandler(PGHandler())

    return logger
