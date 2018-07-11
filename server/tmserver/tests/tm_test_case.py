import os
import unittest

import pytest

from ..migrations import reset_db
from ..world import GameWorld

class TildemushUnitTestCase(unittest.TestCase):
    def setUp(self):
        if os.environ.get('TILDEMUSH_ENV') != 'test':
            pytest.exit('Run tildemush tests with TILDEMUSH_ENV=test')

class TildemushTestCase(TildemushUnitTestCase):
    def setUp(self):
        super().setUp()

        reset_db()
        GameWorld.reset()
