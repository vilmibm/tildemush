import sys

import click

from .core import GameServer
from .logs import pg_logger, debug_logger


@click.command()
@click.option('--debug', default=False, help='Log to STDOUT.')
def _main(debug):
    logger = pg_logger
    if debug is True:
        logger = debug_logger

    gs = GameServer(logger=logger)
    gs.start()


def main():
    try:
        _main()
    except KeyboardInterrupt:
        rc = 0
    except Exception as e:
        print('tildemush server died: {}'.format(e), file=sys.stderr)
        rc = 1
    else:
        rc = 0

    exit(rc)
