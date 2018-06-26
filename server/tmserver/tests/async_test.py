import os
import asyncio
import json
from unittest import mock

import pytest
import websockets

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
    await client.recv()
    await client.send('COMMAND say hello')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg == 'vilmibm says, "hello"'
    await client.close()

async def setup_user(client, username, god=False):
    await client.send('REGISTER {}:foobarbazquux'.format(username))
    await client.recv()

    if god:
        ua = UserAccount.get(UserAccount.username==username)
        ua.is_god = True
        ua.save()

    await client.send('LOGIN {}:foobarbazquux'.format(username))
    # once for LOGIN OK
    await client.recv()
    # once for the client state update
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
            (witch "horse"
              (has {"num-pets" 0
                    "name" "snoozy"
                    "description" "a horse"})
              (hears "pet"
                (set-data "num-pets" (+ 1 (get-data "num-pets")))
                  (if (= 0 (% (get-data "num-pets") 5))
                    (says "neigh neigh neigh i am horse"))))''')
    snoozy = GameObject.create(
        author=vil,
        shortname='snoozy',
        script_revision=script_rev)
    foyer = GameObject.get(GameObject.shortname=='foyer')
    GameWorld.put_into(foyer, snoozy)
    for _ in range(0, 4):
        await client.send('COMMAND pet')
        msg = await client.recv()
        assert msg == 'COMMAND OK'
    await client.send('COMMAND pet')
    await client.recv()
    msg = await client.recv()
    assert msg == 'snoozy says, "neigh neigh neigh i am horse"'
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
    cigar = GameObject.create_scripted_object(
        'item', vil, 'cigar', {
            'name': 'cigar',
            'description': 'a fancy cigar ready for lighting'})
    phone = GameObject.create(author=vil, shortname='smartphone')
    app = GameObject.create_scripted_object(
        'item', vil, 'kwam', {
            'name': 'Kwam',
            'description': 'A smartphone application for KWAM'})
    foyer = GameObject.get(GameObject.shortname=='foyer')
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
async def test_client_state(event_loop, mock_logger, client):
    await client.send('REGISTER vilmibm:foobarbazquux')
    await client.recv()

    vilmibm = UserAccount.get(UserAccount.username=='vilmibm')
    god = UserAccount.get(UserAccount.username=='god')

    room = GameObject.create_scripted_object(
        'room', god, 'ten-forward', dict(
            name='ten forward',
            description='the bar lounge of the starship enterprise.'))
    quadchess = GameObject.create_scripted_object(
        'item', god, 'quadchess', dict(
            name='quadchess',
            description='a chess game with four decks'))
    chess_piece = GameObject.create_scripted_object(
        'item', god, 'chess-piece', dict(
            name='chess piece',
            description='a chess piece. Looks like a bishop.'))
    drink = GameObject.create_scripted_object(
        'item', god, 'weird-drink', dict(
            name='weird drink',
            description='an in-house invention of Guinan. It is purple and fizzes ominously.'))
    tricorder = GameObject.create_scripted_object(
        'item', god, 'tricorder', dict(
            name='tricorder',
            description='looks like someone left their tricorder here.'))
    medical_app = GameObject.create_scripted_object(
        'item', god, 'medical-program', dict(
            name='medical program',
            description='you can use this to scan or call up data about a patient.'))
    patient_file = GameObject.create_scripted_object(
        'item', god, 'patient-file', dict(
            name='patient file',
            description='a scan of Lt Barclay'))
    phase_analyzer_app = GameObject.create_scripted_object(
        'item', god, 'phase-analyzer-program', dict(
            name='phase analyzer program',
            description='you can use this to scan for phase shift anomalies'))
    music_app = GameObject.create_scripted_object(
        'item', god, 'media-app', dict(
            name='media app',
            description='this program turns your tricorder into a jukebox'))
    klingon_opera = GameObject.create_scripted_object(
        'item', god, 'klingon-opera-music', dict(
            name='klingon opera music',
            description='a recording of a klingon opera'))
    GameWorld.put_into(room, quadchess)
    GameWorld.put_into(quadchess, chess_piece)
    GameWorld.put_into(room, drink)
    GameWorld.put_into(vilmibm.player_obj, tricorder)
    GameWorld.put_into(tricorder, medical_app)
    GameWorld.put_into(medical_app, patient_file)
    GameWorld.put_into(tricorder, phase_analyzer_app)
    GameWorld.put_into(tricorder, music_app)
    GameWorld.put_into(music_app, klingon_opera)

    GameObject.create_scripted_object(
        'room', god, 'jeffries-tube-god', dict(
            name='Jeffries Tube',
            description='A cramped little space used for maintenance.'))
    GameObject.create_scripted_object(
        'room', god, 'replicator-room-god', dict(
            name='Replicator Room',
            description="Little more than a closet, you can use this room to interact with the replicator in case you don't want to make an order a the bar."))

    GameWorld.put_into(room, god.player_obj)
    GameWorld.create_exit(
        god.player_obj,
        'Sliding Door',
        'east replicator-room-god An automatic, shiny sliding door')
    GameWorld.create_exit(
        god.player_obj,
        'Hatch',
        'below jeffries-tube-god A small hatch, just big enough for a medium sized humanoid.')
    GameWorld.remove_from(room, god.player_obj)

    await client.send('LOGIN vilmibm:foobarbazquux')
    await client.recv()
    await client.recv()

    GameWorld.put_into(room, vilmibm.player_obj)

    data_msg = await client.recv()
    assert data_msg.startswith('STATE ')
    payload = json.loads(data_msg[len('STATE '):])
    assert payload == {
        'motd': 'welcome to tildemush',
        'user': {
            'username': 'vilmibm',
            'display_name': 'vilmibm',
            'description': 'a gaseous cloud'
        },
        'room': {
            'name': 'ten forward',
            'description': 'the bar lounge of the starship enterprise.',
            'contains': [
                {'name': 'quadchess',
                 'description': 'a chess game with four decks'},
                {'name': 'weird drink',
                 'description': 'an in-house invention of Guinan. It is purple and fizzes ominously.'},
                {'name': 'Sliding Door',
                 'description': 'An automatic, shiny sliding door'},
                {'name': 'Hatch',
                 'description': 'A small hatch, just big enough for a medium sized humanoid.'}
            ],
            'exits': {
                'east': {
                    'exit_name': 'Sliding Door',
                    'room_name': 'Replicator Room'},
                'below': {
                    'exit_name': 'Hatch',
                    'room_name': 'Jeffries Tube'}}
        },
        'inventory': [
            {'name':'tricorder',
             'description': 'looks like someone left their tricorder here.',
             'contains': [
                 {'name': 'medical program',
                  'description': 'you can use this to scan or call up data about a patient.',
                  'contains': [{'name': 'patient file',
                                'description': 'a scan of Lt Barclay',
                                'contains': []}]},
                 {'name': 'phase analyzer program',
                  'description': 'you can use this to scan for phase shift anomalies',
                  'contains': []},
                 {'name': 'media app',
                  'description': 'this program turns your tricorder into a jukebox',
                  'contains': [
                      {'name': 'klingon opera music',
                       'description': 'a recording of a klingon opera',
                       'contains': []}]}]}
        ],
        'scripts': ['vilmibm-sanctum', 'vilmibm']
    }
    await client.close()

@pytest.mark.asyncio
async def test_create_item(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    await client.send('COMMAND create item "A fresh cigar" An untouched black and mild with a wood tip')
    msg = await client.recv()
    assert msg == 'COMMAND OK'

    msg = await client.recv()
    assert msg.startswith('STATE')

    msg = await client.recv()
    assert msg == 'You breathed light into a whole new item. Its true name is vilmibm/a-fresh-cigar'

    # create a dupe
    await client.send('COMMAND create item "A fresh cigar" An untouched black and mild with a wood tip')
    msg = await client.recv()
    assert msg == 'COMMAND OK'

    msg = await client.recv()
    assert msg.startswith('STATE')

    msg = await client.recv()
    assert msg == 'You breathed light into a whole new item. Its true name is vilmibm/a-fresh-cigar-3'

    cigar = GameObject.get_or_none(GameObject.shortname=='vilmibm/a-fresh-cigar')
    dupe = GameObject.get_or_none(GameObject.shortname=='vilmibm/a-fresh-cigar-3')

    assert cigar is not None
    assert dupe is not None

    assert 'A fresh cigar' == cigar.get_data('name')
    assert 'A fresh cigar' == dupe.get_data('name')
    assert 'An untouched black and mild with a wood tip' == cigar.get_data('description')
    assert 'An untouched black and mild with a wood tip' == dupe.get_data('description')

    await client.close()

@pytest.mark.asyncio
async def test_create_room(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    await client.send('COMMAND create room "Crystal Cube" A cube-shaped room made entirely of crystal.')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('You breathed light into a whole new room')

    sanctum = GameObject.get(
        GameObject.author==vil,
        GameObject.is_sanctum==True
    )
    GameWorld.put_into(sanctum, vil.player_obj)
    msg = await client.recv()
    assert msg.startswith('STATE')
    # TODO eventually when we have transitive commands, touch the actual right
    # thing. For now, only one thing should be touchable.
    await client.send('COMMAND touch')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg.startswith('You materialize')

    await client.close()

@pytest.mark.asyncio
async def test_create_oneway_exit(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    sanctum = GameObject.get(
        GameObject.author==vil,
        GameObject.is_sanctum==True
    )
    GameWorld.put_into(sanctum, vil.player_obj)
    msg = await client.recv()
    assert msg.startswith('STATE')
    await client.send('COMMAND create exit "Rusty Door" east foyer A rusted, metal door')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('You breathed light into a whole new exit')
    await client.send('COMMAND go east')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg.startswith('You materialize')

    foyer = GameObject.get(GameObject.shortname=='foyer')
    assert vil.player_obj in foyer.contains

    await client.close()

@pytest.mark.asyncio
async def test_create_twoway_exit_between_owned_rooms(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    sanctum = GameObject.get(
        GameObject.author==vil,
        GameObject.is_sanctum==True
    )
    GameWorld.put_into(sanctum, vil.player_obj)
    msg = await client.recv()
    assert msg.startswith('STATE')

    await client.send('COMMAND create room "Crystal Cube" A cube-shaped room made entirely of crystal.')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('You breathed light into a whole new room')

    cube = GameObject.get(GameObject.shortname.startswith('vilmibm/crystal-cube'))

    await client.send(
        'COMMAND create exit "Rusty Door" east {} A rusted, metal door'.format(cube.shortname))
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('You breathed light into a whole new exit')

    await client.send('COMMAND go east')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg.startswith('You materialize')

    assert vil.player_obj in cube.contains
    assert vil.player_obj not in sanctum.contains

    await client.send('COMMAND go west')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg.startswith('You materialize')

    assert vil.player_obj not in cube.contains
    assert vil.player_obj in sanctum.contains

    await client.close()

# TODO the following inventory tests should really be in their own file. in general
# this file has become a giant monster and needs serious help; either with
# splitting up into smaller files or helpers that reduce some of the async recv
# redundancy

@pytest.mark.asyncio
async def test_handle_get(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    foyer = GameObject.get(GameObject.shortname == 'foyer')

    cigar = GameObject.create_scripted_object(
        'item', vil, 'vilmibm/a-fresh-cigar', dict(
            name='A fresh cigar',
            description='smoke it if you want'))

    GameWorld.put_into(foyer, cigar)

    await client.send('COMMAND get cigar')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg.startswith('STATE')

    msg = await client.recv()
    assert msg == 'You grab A fresh cigar.'

    vil_obj = GameObject.get(GameObject.shortname=='vilmibm')
    assert 'A fresh cigar' in [o.name for o in vil_obj.contains]

    await client.close()

@pytest.mark.asyncio
async def test_handle_get_denied(event_loop, mock_logger, client):
    god = UserAccount.get(UserAccount.username=='god')
    foyer = GameObject.get(GameObject.shortname=='foyer')
    phaser = GameObject.create_scripted_object(
        'item', god, 'phaser-god', dict(
            name='a phaser',
            description='watch where u point it'))

    phaser.set_perm('carry', 'owner')

    GameWorld.put_into(foyer, phaser)

    await setup_user(client, 'vilmibm')

    await client.send('COMMAND get phaser')
    msg = await client.recv()
    assert msg == 'ERROR: You grab a hold of a phaser but no matter how hard you pull it stays rooted in place.'

    await client.close()

@pytest.mark.asyncio
async def test_handle_drop(event_loop, mock_logger, client):
    god = UserAccount.get(UserAccount.username=='god')
    foyer = GameObject.get(GameObject.shortname=='foyer')
    phaser = GameObject.create_scripted_object(
        'item', god, 'phaser-god', dict(
            name='a phaser',
            description='watch where u point it'))

    GameWorld.put_into(foyer, phaser)

    await setup_user(client, 'vilmibm')

    await client.send('COMMAND get phaser')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg.startswith('STATE')

    msg = await client.recv()
    assert msg == 'You grab a phaser.'

    await client.send('COMMAND drop phaser')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg == 'You drop a phaser.'

    vil_obj = GameObject.get(GameObject.shortname=='vilmibm')
    assert 'a phaser' not in [o.name for o in vil_obj.contains]

    await client.close()

@pytest.mark.asyncio
async def test_handle_put(event_loop, mock_logger, client):
    god = UserAccount.get(UserAccount.username=='god')
    foyer = GameObject.get(GameObject.shortname=='foyer')
    phaser = GameObject.create_scripted_object(
        'item', god, 'phaser-god', dict(
            name='a phaser',
            description='watch where u point it'))
    space_chest = GameObject.create_scripted_object(
        'item', god, 'space-chest-god', dict(
            name='Fancy Space Chest',
            description="It's like a fantasy chest but palette swapped."))

    phaser.set_perm('carry', 'world')
    space_chest.set_perm('execute', 'world')

    GameWorld.put_into(foyer, phaser)
    GameWorld.put_into(foyer, space_chest)

    await setup_user(client, 'vilmibm')

    await client.send('COMMAND put phaser in chest')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg == 'You put a phaser in Fancy Space Chest'

    await client.close()

@pytest.mark.asyncio
async def test_handle_remove(event_loop, mock_logger, client):
    god = UserAccount.get(UserAccount.username=='god')
    foyer = GameObject.get(GameObject.shortname=='foyer')
    phaser = GameObject.create_scripted_object(
        'item', god, 'phaser-god', dict(
            name='a phaser',
            description='watch where u point it'))
    space_chest = GameObject.create_scripted_object(
        'item', god, 'space-chest-god', dict(
            name='Fancy Space Chest',
            description="It's like a fantasy chest but palette swapped."))

    phaser.set_perm('carry', 'world')
    space_chest.set_perm('execute', 'world')

    GameWorld.put_into(foyer, space_chest)
    GameWorld.put_into(space_chest, phaser)

    await setup_user(client, 'vilmibm')

    await client.send('COMMAND remove phaser from chest')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg == 'You remove a phaser from Fancy Space Chest and carry it with you.'

    await client.close()


@pytest.mark.asyncio
async def test_create_twoway_exit_via_world_perms(event_loop, mock_logger, client):
    await setup_user(client, 'vilmibm')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    foyer = GameObject.get(GameObject.shortname=='foyer')
    foyer.set_perm('write', 'world')

    await client.send('COMMAND create room "Crystal Cube" a cube-shaped room made entirely of crystal.')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('You breathed light into a whole new room')

    cube = GameObject.get(GameObject.shortname.startswith('vilmibm/crystal-cube'))

    await client.send(
        'COMMAND create exit "Rusty Door" east {} A rusted, metal door'.format(cube.shortname))
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('You breathed light into a whole new exit')

    await client.send('COMMAND go east')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg.startswith('You materialize')

    assert vil.player_obj in cube.contains
    assert vil.player_obj not in foyer.contains

    await client.send('COMMAND go west')
    msg = await client.recv()
    assert msg == 'COMMAND OK'
    msg = await client.recv()
    assert msg.startswith('STATE')
    msg = await client.recv()
    assert msg.startswith('You materialize')

    assert vil.player_obj not in cube.contains
    assert vil.player_obj in foyer.contains

    await client.close()
