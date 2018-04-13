import logging
import unittest.mock as mock
import unittest

from ..logs import PGHandler, get_logger
from ..migrations import reset_db
from ..models import Log
from .tm_test_case import TildemushTestCase


class TestPGHandler(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.pgh = PGHandler()
        self.mock_log_record = mock.Mock()
        self.mock_log_record.getMessage.return_value = 'sweet'
        self.mock_log_record.levelname = 'INFO'

    def test_respects_env(self):
        self.assertEqual('test', self.pgh.env)

    def test_sets_created_at(self):
        self.pgh.emit(self.mock_log_record)
        logs = Log.select()
        self.assertIsNotNone(logs[0].created_at)

    def test_levels(self):
        self.pgh.emit(self.mock_log_record)
        logs = Log.select()
        self.assertEqual(logs[0].level, 'INFO')

    def test_msg(self):
        self.pgh.emit(self.mock_log_record)
        logs = Log.select()
        self.assertEqual(logs[0].raw, 'sweet')


class TestLogging(TildemushTestCase):
    def test_debug_ignores_pg(self):
        with mock.patch('logging.getLogger') as m:
            logger = get_logger(debug=True)

        self.assertFalse(m.return_value.addHandler.called)

    def test_defaults_to_pg(self):
        with mock.patch('logging.getLogger') as m:
            logger = get_logger()
        self.assertTrue(m.return_value.addHandler.called)


