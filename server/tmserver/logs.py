import logging

# TODO this will eventually be using postgresql. just to get off the ground,
# it's basic stdout logging for now.

logging.basicConfig(level=logging.INFO)

debug_logger = logging.getLogger('tmserver debug')
pg_logger = logging.getLogger('tmserver')

debug_logger.addHandler(logging.StreamHandler())

# TODO write PGHandler
