import unittest.mock as mock
import unittest

from ..migrations import reset_db
from ..models import Log

# TODO these tests should test the postgresql logging handler, not that we log where we expect to log.

class TestPGHandler(unittest.TestCase):
    def setUp(self):
        reset_db()

    def test_respects_env(self):
        pass

    def test_sets_created_at(self):
        pass

    def test_levels(self):
        pass


# TODO this testcase ensures that get_logger works as expected

class TestLogging(unittest.TestCase):
    def test_debug_ignores_pg(self):
        pass

