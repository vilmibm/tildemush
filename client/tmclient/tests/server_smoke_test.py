import io
import os
import unittest
from unittest import mock

import pytest

from ..client import Client
from ..screens import quit_client
from tmserver.core import GameServer, LOOP
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
        self.client = Client()
        self.boot_server()
        self.boot_client()

    def tearDown(self):
        self.kill_client()
        self.kill_server()

    def boot_server(self):
        self.mock_server_logger = mock.Mock()
        GameServer(GameWorld, logger=self.mock_server_logger).start()

    def kill_server(self):
        LOOP.stop()

    def boot_client(self):
        mock_stdout = io.StringIO()
        mock_stdin = io.StringIO()
        with mock.patch('sys.stdout', mock_stdout):
            with mock.patch('sys.stdin', mock_stdin):
                self.client.run()

    def kill_client(self):
        quit_client()

    @pytest.mark.asyncio
    def test_registration(self):
        pass

    @pytest.mark.asyncio
    def test_logging_in(self):
        pass

    @pytest.mark.asyncio
    def test_error_popup(self):
        pass

    @pytest.mark.asyncio
    def test_send_game_command(self):
        pass
