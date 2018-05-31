import os
import unittest

import pytest

from ..migrations import reset_db
from ..game_world import GameWorld


class TildemushTestCase(unittest.TestCase):
    def setUp(self):
        if os.environ.get('TILDEMUSH_ENV') != 'test':
            pytest.exit('Run tildemush tests with TILDEMUSH_ENV=test')

        reset_db()
        GameWorld.reset()
