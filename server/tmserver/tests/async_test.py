import os
import asyncio
import json
from unittest import mock

import pytest
import websockets

from .tm_test_case import TildemushTestCase
from ..core import GameServer
from ..migrations import reset_db
from ..models import UserAccount, Script, GameObject, ScriptRevision
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
    server_future = gs._get_ws_server()
    asyncio.ensure_future(server_future, loop=event_loop)
    yield
    server_future.ws_server.server.close()

@pytest.fixture
async def client(event_loop):
    client = await websockets.connect('ws://localhost:5555', loop=event_loop)
    yield client
    # TODO this is getting called after the server is closed :( if we can fix
    # the ordering, the client.close()s can come out of the test functions
    await client.close()

@pytest.mark.asyncio
async def test_garbage(event_loop, mock_logger, client):
    await client.send('GARBAGE')
    msg = await client.recv()
    assert msg == 'ERROR: message not understood'
    await client.close()

@pytest.mark.asyncio
async def test_ping(event_loop, mock_logger, client):
    await client.send('PING')
    msg = await client.recv()
    assert msg == 'PONG'
    await client.close()

@pytest.mark.asyncio
async def test_registration_success(event_loop, mock_logger, client):
    await client.send('REGISTER vilmibm:foobarbazquux')
    msg = await client.recv()
    assert msg == 'REGISTER OK'
    await client.close()

@pytest.mark.asyncio
async def test_registration_error(event_loop, mock_logger, client):
    await client.send('REGISTER vilmibm:foo')
    msg = await client.recv()
    assert msg == 'ERROR: password too short'
    await client.close()

@pytest.mark.asyncio
async def test_login_success(event_loop, mock_logger, client):
    await client.send('REGISTER vilmibm:foobarbazquux')
    await client.recv()
    await client.send('LOGIN vilmibm:foobarbazquux')
    msg = await client.recv()
    assert msg == 'LOGIN OK'
    await client.close()

@pytest.mark.asyncio
async def test_login_error(event_loop, mock_logger, client):
    await client.send('REGISTER vilmibm:foobarbazquux')
    await client.recv()
    await client.send('LOGIN evilmibm:foobarbazquux')
    msg = await client.recv()
    assert msg == 'ERROR: no such user'
    await client.close()

@pytest.mark.asyncio
async def test_game_command(event_loop, mock_logger, client):
    await client.send('REGISTER vilmibm:foobarbazquux')
    await client.recv()
    await client.send('LOGIN vilmibm:foobarbazquux')
    await client.recv()
    await client.send('COMMAND say hello')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg == 'vilmibm says hello'
    await client.close()

async def setup_user(client, username, god=False):
    await client.send('REGISTER {}:foobarbazquux'.format(username))
    await client.recv()

    if god:
        ua = UserAccount.get(UserAccount.username==username)
        ua.god = True
        ua.save()

    await client.send('LOGIN {}:foobarbazquux'.format(username))
    await client.recv()


@pytest.mark.asyncio
async def test_announce_forbidden(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    await client.send('COMMAND announce HELLO EVERYONE')
    msg = await client.recv()
    assert msg == 'ERROR: you are not powerful enough to do that.'
    await client.close()

@pytest.mark.asyncio
async def test_announce(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm', god=True)
    snoozy_client = await websockets.connect('ws://localhost:5555', loop=event_loop)
    await setup_user(snoozy_client, 'snoozy')
    await client.send('COMMAND announce HELLO EVERYONE')
    vil_msg = await client.recv()
    assert vil_msg == 'COMMAND OK'
    snoozy_msg = await snoozy_client.recv()
    assert snoozy_msg == "The very air around you seems to shake as vilmibm's booming voice says HELLO EVERYONE"
    await snoozy_client.close()
    await client.close()

@pytest.mark.asyncio
async def test_witch_script(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm', god=True)
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    horse_script = Script.create(
        name='horse',
        author=vil)
    script_rev = ScriptRevision.create(
        script=horse_script,
        code='''
            (witch "horse" by "vilmibm"
              (has {"num-pets" 0})
              (hears "pet"
                (set-data "num-pets" (+ 1 (get-data "num-pets")))
                  (if (= 0 (% (get-data "num-pets") 5))
                    (says "neigh neigh neigh i am horse"))))''')
    snoozy = GameObject.create(
        author=vil,
        name='snoozy',
        script_revision=script_rev)
    foyer = GameObject.get(GameObject.name=='Foyer')
    GameWorld.put_into(foyer, snoozy)
    for _ in range(0, 4):
        await client.send('COMMAND pet')
        msg = await client.recv()
        assert msg == 'COMMAND OK'
    await client.send('COMMAND pet')
    await client.recv()
    msg = await client.recv()
    assert msg == 'snoozy says neigh neigh neigh i am horse'
    await client.close()


# TODO lookup if i can do a websocket client as context manager, i think i can?

@pytest.mark.asyncio
async def test_whisper_no_args(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    await client.send('COMMAND whisper')
    msg = await client.recv()
    assert msg == 'ERROR: try /whisper another_username some cool message'
    await client.close()

@pytest.mark.asyncio
async def test_whisper_no_msg(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    await client.send('COMMAND whisper snoozy')
    msg = await client.recv()
    assert msg == 'ERROR: try /whisper another_username some cool message'
    await client.close()

@pytest.mark.asyncio
async def test_whisper_bad_target(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    await client.send('COMMAND whisper snoozy hey what are the haps')
    msg = await client.recv()
    assert msg == 'ERROR: there is nothing named snoozy near you'
    await client.close()

@pytest.mark.asyncio
async def test_whisper(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    snoozy_client = await websockets.connect('ws://localhost:5555', loop=event_loop)
    await setup_user(snoozy_client, 'snoozy')
    await client.send('COMMAND whisper snoozy hey here is a conspiracy')
    vil_msg = await client.recv()
    assert vil_msg == 'COMMAND OK'
    snoozy_msg = await snoozy_client.recv()
    assert snoozy_msg == "vilmibm whispers so only you can hear: hey here is a conspiracy"
    await snoozy_client.close()
    await client.close()


@pytest.mark.asyncio
async def test_look(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    snoozy_client = await websockets.connect('ws://localhost:5555', loop=event_loop)
    await setup_user(snoozy_client, 'snoozy')
    cigar = GameObject.create(
        author=vil,
        name='cigar',
        description='a fancy cigar ready for lighting')
    phone = GameObject.create(
        author=vil,
        name='smartphone')
    app = GameObject.create(
        author=vil,
        name='Kwam',
        description='A smartphone application for KWAM')
    foyer = GameObject.get(GameObject.name=='Foyer')
    GameWorld.put_into(foyer, phone)
    GameWorld.put_into(foyer, cigar)
    GameWorld.put_into(phone, app)

    await client.send('COMMAND look')
    # we expect 4 messages: snoozy, room, phone, cigar. we *shouldn't* see app.
    msgs = set()
    for _ in range(0, 4):
        msgs.add(await client.recv())
    assert {'You are in the Foyer, {}'.format(foyer.description),
            'You see a cigar, a fancy cigar ready for lighting',
            'You see a smartphone',
            'You see snoozy, a gaseous cloud'}
    await client.close()
    await snoozy_client.close()

@pytest.mark.asyncio
async def test_data_malformed_path(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    bad_data = [
        'DATA',
        'DATA roominfo funtimes',
        'DATAroominfo']
    for bad in bad_data:
        await client.send(bad)
        msg = await client.recv()
        assert msg == 'ERROR: malformed data request: {}'.format(bad)

    await client.close()

@pytest.mark.asyncio
async def test_data_unknown_path(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')

    await client.send('DATA ぶぶぶぶぶぶぶ')
    msg = await client.recv()
    assert msg == 'ERROR: Unknown data API path ぶぶぶぶぶぶぶ'

    await client.close()

@pytest.mark.asyncio
async def test_roominfo(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    foyer = GameObject.get(GameObject.name=='Foyer')
    cigar = GameObject.create(
        author=vil,
        name='cigar',
        description='a fancy cigar ready for lighting')
    GameWorld.put_into(foyer, cigar)
    await client.send('DATA roominfo')
    msg = await client.recv()
    assert msg.startswith('DATA roominfo')
    payload = msg.split(' ', maxsplit=2)[2]
    payload = json.loads(payload)
    assert payload['name'] == foyer.name
    assert payload['description'] == foyer.description
    assert payload['objects'] == [
        {'name': 'vilmibm',
         'description': 'a gaseous cloud'},
        {'name': 'cigar',
         'description': 'a fancy cigar ready for lighting'}]
    await client.close()

@pytest.mark.asyncio
async def test_playerinfo(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    await client.send('DATA playerinfo')
    msg = await client.recv()
    assert msg.startswith('DATA playerinfo')
    payload = msg.split(' ', maxsplit=2)[2]
    payload = json.loads(payload)
    assert payload == {
        'username': vil.username,
        'playername': vil.player_obj.name,
        'description': vil.player_obj.description
    }
    await client.close()
