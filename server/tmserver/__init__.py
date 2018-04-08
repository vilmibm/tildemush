import sys

import click

from .core import GameServer
from .logs import get_logger


@click.command()
@click.option('--debug/--no-debug', default=False, help='Log to the console.')
def _main(debug):
    gs = GameServer(logger=get_logger(debug))
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
