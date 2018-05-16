import asyncio
from unittest import mock

import pytest
import websockets

from .tm_test_case import TildemushTestCase
from ..core import GameServer
from ..world import GameWorld

@pytest.fixture
def mock_logger():
    yield mock.Mock()

@pytest.mark.asyncio
async def test_ping(event_loop, mock_logger):
    gs = GameServer(GameWorld, loop=event_loop, logger=mock_logger, port=5555)
    asyncio.ensure_future(gs._get_ws_server(), loop=event_loop)
    client = await websockets.connect('ws://localhost:5555')
    await client.send('PING')
    msg = await client.recv()
    assert msg == 'PONG'
    await client.close()


# TODO test registration
# TODO test login
# TODO test game commands
