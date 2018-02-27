import logging
import sys

# TODO this will eventually be using postgresql. just to get off the ground,
# it's basic stdout logging for now.

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger('tmserver')
