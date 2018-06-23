import sys

import click

from .core import GameServer
from .logs import get_logger
from .world import GameWorld
from .migrations import init_db


@click.command()
@click.option('--debug/--no-debug', default=False, help='Log to the console.')
@click.option('--bind', default='127.0.0.1', help='bind IP')
@click.option('--port', default=10014, help='server port')
def _main(debug, bind, port):
    gs = GameServer(GameWorld, logger=get_logger(debug), bind=bind, port=port)
    init_db()
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
