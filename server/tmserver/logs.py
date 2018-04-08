import os
import logging

from .models import Log

logging.basicConfig(level=logging.INFO)

class PGHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)
        self.env = os.environ.get('TILDEMUSH_ENV', 'live')

    def emit(self, record):
        # TODO there may end up being a bit of a skew between when a call to
        # log is issued and when the created_at is set for a Log record. For
        # the sake of expediency i'm ok with that, but if it ends up being an
        # issue this should parse and use record.created
        Log.create(
            env=self.env,
            raw=record.getMessage(),
            level=record.levelname)

# TODO looking good, but debug logger still going -- i think stdout handler is still active? figure that out
debug_logger = logging.getLogger('tmserver debug')
pg_logger = logging.getLogger('tmserver')
pg_logger.addHandler(PGHandler())
