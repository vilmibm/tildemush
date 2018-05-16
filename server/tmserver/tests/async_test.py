import os
import asyncio
from unittest import mock

import pytest
import websockets

from .tm_test_case import TildemushTestCase
from ..core import GameServer
from ..migrations import reset_db
from ..world import GameWorld

@pytest.fixture(autouse=True)
def state():
    if os.environ.get('TILDEMUSH_ENV') != 'test':
        pytest.exit('Run tildemush tests with TILDEMUSH_ENV=test')

    reset_db()
    GameWorld.reset()

@pytest.fixture
def mock_logger():
    yield mock.Mock()

@pytest.fixture(autouse=True)
def start_server(event_loop, mock_logger):
    gs = GameServer(GameWorld, loop=event_loop, logger=mock_logger, port=5555)
    asyncio.ensure_future(gs._get_ws_server(), loop=event_loop)

@pytest.mark.asyncio
async def test_ping(event_loop, mock_logger):
    client = await websockets.connect('ws://localhost:5555')
    await client.send('PING')
    msg = await client.recv()
    assert msg == 'PONG'
    await client.close()


# TODO test registration
# TODO test login
# TODO test game commands
