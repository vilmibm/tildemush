import os
import unittest

import pytest

from tmserver.migrations import reset_db
from tmserver.world import GameWorld


class ServerSmokeTest(unittest.TestCase):
    # TODO this is copypasta from server. as it's seeming increasingly like
    # we'll want a tmcommon package, the TildemushTestCase ought to live there
    # when it exists.
    def setUp(self):
        if os.environ.get('TILDEMUSH_ENV') != 'test':
            pytest.exit('Run tildemush tests with TILDEMUSH_ENV=test')

        reset_db()
        GameWorld.reset()

    def test_registration(self):
        pass

    def test_logging_in(self):
        pass

    def test_error_popup(self):
        pass

    def test_send_game_command(self):
        pass
