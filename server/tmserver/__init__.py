import sys

from .core import GameServer


def _main(argv):
    gs = GameServer()
    gs.start()


def main():
    try:
        _main(sys.argv)
    except Exception as e:
        print('tildemush server died: {}'.format(e), file=sys.stderr)
        rc = 1
    else:
        rc = 0

    exit(rc)
