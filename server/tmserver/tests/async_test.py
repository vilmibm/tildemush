from unittest import mock

import pytest

from .tm_test_case import TildemushTestCase
from ..core import GameServer


class ServerSmokeTest(TildemushTestCase):

    def setUp(self):
        super().setUp()
        self.boot_server()

    def tearDown(self):
        self.kill_server()

    def boot_server(self):
        self.loop = asyncio.get_event_loop()
        self.mock_server_logger = mock.Mock()
        GameServer(GameWorld, loop=self.loop, logger=self.mock_server_logger, port=5555).start()

    def kill_server(self):
        self.loop.stop()

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
