import os
import asyncio
import json
from unittest import mock

import pytest
import websockets

from ..core import GameServer
from ..migrations import reset_db
from ..models import UserAccount, Script, GameObject, ScriptRevision, Editing, LastSeen, Permission
from ..world import GameWorld

class Client:
    def __init__(self, event_loop):
        self.loop = event_loop

    async def __aenter__(self):
        self.c = await websockets.connect('ws://localhost:5555', loop=self.loop)
        return self

    async def __aexit__(self, et, e, tb):
        await self.c.close()
        await self.c.close()

    async def send(self, string, expected_msgs=[]):
        await self.c.send(string)
        if len(expected_msgs) > 0:
            await self.assert_next(*expected_msgs)

    async def recv(self):
        return await self.c.recv()

    async def assert_next(self, *expected_msgs):
        for expected_msg in expected_msgs:
            msg = await self.recv()
            assert msg.startswith(expected_msg)

    async def assert_recv(self, expected_msg):
        msg = await self.recv()
        assert msg.startswith(expected_msg)
        return msg

    async def assert_set(self, expected_set):
        recvd = set()
        for _ in expected_set:
            recvd.add(await self.recv())
        assert recvd == expected_set

    async def login(self, username, password='foobarbazquux'):
        await self.send('LOGIN {}:foobarbazquux'.format(username))
        # once for LOGIN OK
        await self.recv()
        # once for the client state update
        await self.recv()

    async def quit_game(self):
        await self.send('QUIT')

    async def setup_user(self, username, god=False):
        await self.send('REGISTER {}:foobarbazquux'.format(username))
        await self.recv()

        ua = UserAccount.get(UserAccount.username==username)
        if god:
            ua.is_god = True
            ua.save()

        await self.login(username)

        return ua


@pytest.fixture
async def client(event_loop):
    async with Client(event_loop) as c:
        yield c


@pytest.fixture(autouse=True)
def state(event_loop):
    if os.environ.get('TILDEMUSH_ENV') != 'test':
        pytest.exit('Run tildemush tests with TILDEMUSH_ENV=test')
    reset_db()
    GameWorld.reset()
    gs = GameServer(GameWorld, loop=event_loop, logger=mock.Mock(), port=5555)
    server_future = gs._get_ws_server()
    asyncio.ensure_future(server_future, loop=event_loop)
    yield
    server_future.ws_server.server.close()


@pytest.mark.asyncio
async def test_garbage(client):
    await client.send('GARBAGE', ['ERROR: message not understood'])

@pytest.mark.asyncio
async def test_ping(client):
    await client.send('PING', ['PONG'])

@pytest.mark.asyncio
async def test_registration_success(client):
    await client.send('REGISTER vilmibm:foobarbazquux', ['REGISTER OK'])

@pytest.mark.asyncio
async def test_registration_error(client):
    await client.send('REGISTER vilmibm:foo', ['ERROR: password too short'])

@pytest.mark.asyncio
async def test_login_success(client):
    await client.send('REGISTER vilmibm:foobarbazquux')
    await client.recv()
    await client.send('LOGIN vilmibm:foobarbazquux', ['LOGIN OK'])


@pytest.mark.asyncio
async def test_login_error(client):
    await client.send('REGISTER vilmibm:foobarbazquux')
    await client.recv()
    await client.send('LOGIN evilmibm:foobarbazquux', [
        'ERROR: no such user'])


@pytest.mark.asyncio
async def test_game_command(client):
    await client.setup_user('vilmibm')
    await client.send('COMMAND say hello', [
        'STATE',
        'STATE',
        'COMMAND OK',
        'vilmibm says, "hello"'])


@pytest.mark.asyncio
async def test_announce_forbidden(client):
    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    await client.send('COMMAND announce HELLO EVERYONE', [
         '{red}you are not powerful enough to do that.'])

@pytest.mark.asyncio
async def test_announce(event_loop):
    async with Client(event_loop) as vclient, Client(event_loop) as sclient:
        await vclient.setup_user('vilmibm', god=True)
        await sclient.setup_user('snoozy')
        await vclient.assert_next('STATE', 'STATE', 'STATE', 'STATE', 'snoozy fades')
        await vclient.send('COMMAND announce HELLO EVERYONE', [
            'COMMAND OK',
            "The very air around you seems to shake as vilmibm's booming voice says HELLO EVERYONE"])
        await sclient.assert_next('STATE', 'STATE', "The very air around you seems to shake as vilmibm's booming voice says HELLO EVERYONE")

        # TODO test in between rooms


@pytest.mark.asyncio
async def test_witch_script(client):
    vil = await client.setup_user('vilmibm', god=True)
    await client.assert_next('STATE', 'STATE')
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
    foyer = GameObject.get(GameObject.shortname=='god/foyer')
    GameWorld.put_into(foyer, snoozy)
    await client.assert_next('STATE', 'STATE')
    for _ in range(0, 4):
        await client.send('COMMAND pet', ['COMMAND OK'])
    await client.send('COMMAND pet', [
        'COMMAND OK',  'snoozy says, "neigh neigh neigh i am horse"'])


@pytest.mark.asyncio
async def test_whisper_no_args(client):
    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    await client.send('COMMAND whisper', [
         '{red}try /whisper another_username some cool message'])


@pytest.mark.asyncio
async def test_whisper_no_msg(client):
    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    await client.send('COMMAND whisper snoozy', [
         '{red}try /whisper another_username some cool message'])


@pytest.mark.asyncio
async def test_whisper_bad_target(client):
    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    await client.send('COMMAND whisper snoozy hey what are the haps', [
         '{red}there is nothing named snoozy near you'])


@pytest.mark.asyncio
async def test_whisper(event_loop):
    async with Client(event_loop) as vclient, Client(event_loop) as sclient:
        await vclient.setup_user('vilmibm')
        await vclient.assert_next('STATE', 'STATE')
        await sclient.setup_user('snoozy')
        await sclient.assert_next('STATE', 'STATE')
        await vclient.assert_next('STATE', 'STATE', 'snoozy fades')
        await vclient.send('COMMAND whisper snoozy hey here is a conspiracy', ['COMMAND OK',])
        await sclient.assert_next("vilmibm whispers so only you can hear: hey here is a conspiracy")


@pytest.mark.asyncio
async def test_look(event_loop):
    async with Client(event_loop) as vclient, Client(event_loop) as sclient:
        vil = await vclient.setup_user('vilmibm')
        await vclient.assert_next('STATE', 'STATE')
        await sclient.setup_user('snoozy')
        await sclient.assert_next('STATE', 'STATE')
        await vclient.assert_next('STATE', 'STATE', 'snoozy fades')
        cigar = GameObject.create_scripted_object(
            vil, 'cigar', 'item', {
                'name': 'cigar',
                'description': 'a fancy cigar ready for lighting'})
        phone = GameObject.create_scripted_object(
            vil, 'smartphone', 'item', dict(
                name='smartphone',
                description='the devil'))
        app = GameObject.create_scripted_object(
            vil, 'kwam', 'item', {
                'name': 'Kwam',
                'description': 'A smartphone application for KWAM'})
        foyer = GameObject.get(GameObject.shortname=='god/foyer')
        GameWorld.put_into(foyer, phone)
        GameWorld.put_into(foyer, cigar)
        GameWorld.put_into(phone, app)
        await vclient.assert_next('STATE', 'STATE', 'STATE', 'STATE')

        await vclient.send('COMMAND look', ['COMMAND OK'])
        await vclient.assert_set({'You see vilmibm, a gaseous cloud',
                                  'You are in the Foyer, {}'.format(foyer.description),
                                  'You see a cigar, a fancy cigar ready for lighting',
                                  'You see a smartphone, the devil',
                                  'You see snoozy, a gaseous cloud'})


@pytest.mark.asyncio
async def test_client_state(client):
    await client.send('REGISTER vilmibm:foobarbazquux')
    await client.recv()

    vilmibm = UserAccount.get(UserAccount.username=='vilmibm')
    god = UserAccount.get(UserAccount.username=='god')

    room = GameObject.create_scripted_object(
        god, 'god/ten-forward', 'room', dict(
            name='ten forward',
            description='the bar lounge of the starship enterprise.'))
    quadchess = GameObject.create_scripted_object(
        god, 'god/quadchess', 'item', dict(
            name='quadchess',
            description='a chess game with four decks'))
    chess_piece = GameObject.create_scripted_object(
        god, 'god/chess-piece', 'item', dict(
            name='chess piece',
            description='a chess piece. Looks like a bishop.'))
    drink = GameObject.create_scripted_object(
        god, 'god/weird-drink', 'item', dict(
            name='weird drink',
            description='an in-house invention of Guinan. It is purple and fizzes ominously.'))
    tricorder = GameObject.create_scripted_object(
        god, 'god/tricorder', 'item', dict(
            name='tricorder',
            description='looks like someone left their tricorder here.'))
    medical_app = GameObject.create_scripted_object(
        god, 'god/medical-program', 'item', dict(
            name='medical program',
            description='you can use this to scan or call up data about a patient.'))
    patient_file = GameObject.create_scripted_object(
        god, 'god/patient-file', 'item', dict(
            name='patient file',
            description='a scan of Lt Barclay'))
    phase_analyzer_app = GameObject.create_scripted_object(
        god, 'god/phase-analyzer-program', 'item', dict(
            name='phase analyzer program',
            description='you can use this to scan for phase shift anomalies'))
    music_app = GameObject.create_scripted_object(
        god, 'god/media-app', 'item', dict(
            name='media app',
            description='this program turns your tricorder into a jukebox'))
    klingon_opera = GameObject.create_scripted_object(
        god, 'god/klingon-opera-music', 'item', dict(
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
        god, 'god/jeffries-tube', 'room', dict(
            name='Jeffries Tube',
            description='A cramped little space used for maintenance.'))
    GameObject.create_scripted_object(
        god, 'god/replicator-room', 'room', dict(
            name='Replicator Room',
            description="Little more than a closet, you can use this room to interact with the replicator in case you don't want to make an order a the bar."))

    GameWorld.put_into(room, god.player_obj)
    GameWorld.create_exit(
        god.player_obj,
        'Sliding Door',
        'east god/replicator-room An automatic, shiny sliding door')
    GameWorld.create_exit(
        god.player_obj,
        'Hatch',
        'below god/jeffries-tube A small hatch, just big enough for a medium sized humanoid.')
    GameWorld.remove_from(room, god.player_obj)

    await client.send('LOGIN vilmibm:foobarbazquux')
    await client.recv()
    await client.recv()

    GameWorld.put_into(room, vilmibm.player_obj)
    await client.assert_next('STATE', 'STATE')

    data_msg = await client.assert_recv('STATE')
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
            'shortname': 'god/ten-forward',
            'description': 'the bar lounge of the starship enterprise.',
            'contains': [
                {'name': 'quadchess',
                 'shortname': 'god/quadchess',
                 'description': 'a chess game with four decks'},
                {'name': 'weird drink',
                 'shortname': 'god/weird-drink',
                 'description': 'an in-house invention of Guinan. It is purple and fizzes ominously.'},
                {'name': 'Sliding Door',
                 'shortname': 'god/sliding-door',
                 'description': 'An automatic, shiny sliding door'},
                {'name': 'Hatch',
                 'shortname': 'god/hatch',
                 'description': 'A small hatch, just big enough for a medium sized humanoid.'},
                {'name': 'vilmibm',
                 'shortname': 'vilmibm',
                 'description': 'a gaseous cloud'}
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
             'shortname': 'god/tricorder',
             'description': 'looks like someone left their tricorder here.',
             'contains': [
                 {'name': 'medical program',
                  'shortname': 'god/medical-program',
                  'description': 'you can use this to scan or call up data about a patient.',
                  'contains': [{'name': 'patient file',
                                'shortname': 'god/patient-file',
                                'description': 'a scan of Lt Barclay',
                                'contains': []}]},
                 {'name': 'phase analyzer program',
                  'shortname': 'god/phase-analyzer-program',
                  'description': 'you can use this to scan for phase shift anomalies',
                  'contains': []},
                 {'name': 'media app',
                  'shortname': 'god/media-app',
                  'description': 'this program turns your tricorder into a jukebox',
                  'contains': [
                      {'name': 'klingon opera music',
                       'shortname': 'god/klingon-opera-music',
                       'description': 'a recording of a klingon opera',
                       'contains': []}]}]}
        ]}

@pytest.mark.asyncio
async def test_create_item(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    await client.send('COMMAND create item "A fresh cigar" An untouched black and mild with a wood tip', [
        'COMMAND OK',
        'STATE',
        'You breathed light into a whole new item. Its true name is vilmibm/a-fresh-cigar'])

    # create a dupe
    await client.send('COMMAND create item "A fresh cigar" An untouched black and mild with a wood tip', [
        'COMMAND OK',
        'STATE',
        'You breathed light into a whole new item. Its true name is vilmibm/a-fresh-cigar-3'])

    cigar = GameObject.get_or_none(GameObject.shortname=='vilmibm/a-fresh-cigar')
    dupe = GameObject.get_or_none(GameObject.shortname=='vilmibm/a-fresh-cigar-3')

    assert cigar is not None
    assert dupe is not None

    assert 'A fresh cigar' == cigar.get_data('name')
    assert 'A fresh cigar' == dupe.get_data('name')
    assert 'An untouched black and mild with a wood tip' == cigar.get_data('description')
    assert 'An untouched black and mild with a wood tip' == dupe.get_data('description')


@pytest.mark.asyncio
async def test_create_room(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    await client.send('COMMAND create room "Crystal Cube" A cube-shaped room made entirely of crystal.', [
        'COMMAND OK',
        'You breathed light into a whole new room'])

    sanctum = GameObject.get(
        GameObject.author==vil,
        GameObject.is_sanctum==True)

    GameWorld.put_into(sanctum, vil.player_obj)

    await client.assert_next('STATE', 'STATE', 'STATE')

    await client.send('COMMAND touch stone', [
        'COMMAND OK', 'STATE', 'STATE', 'STATE',
        'You materialize'])


@pytest.mark.asyncio
async def test_create_oneway_exit(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    sanctum = GameObject.get(
        GameObject.author==vil,
        GameObject.is_sanctum==True)
    GameWorld.put_into(sanctum, vil.player_obj)

    await client.assert_next('STATE', 'STATE', 'STATE')

    await client.send('COMMAND create exit "Rusty Door" east god/foyer A rusted, metal door', [
        'COMMAND OK',
        'STATE',
        'STATE',
        'You breathed light into a whole new exit'])
    await client.send('COMMAND go east', [
        'COMMAND OK',
        'STATE',
        'STATE',
        'STATE',
        'You materialize'])

    foyer = GameObject.get(GameObject.shortname=='god/foyer')
    assert vil.player_obj in foyer.contains


@pytest.mark.asyncio
async def test_create_twoway_exit_between_owned_rooms(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    sanctum = GameObject.get(
        GameObject.author==vil,
        GameObject.is_sanctum==True)

    GameWorld.put_into(sanctum, vil.player_obj)
    await client.assert_next('STATE')

    await client.send('COMMAND create room "Crystal Cube" A cube-shaped room made entirely of crystal.', [
        'STATE',
        'STATE',
        'COMMAND OK',
        'STATE',
        'STATE',
        'You breathed light into a whole new room'])

    cube = GameObject.get(GameObject.shortname.startswith('vilmibm/crystal-cube'))

    await client.send(
        'COMMAND create exit "Rusty Door" east {} A rusted, metal door'.format(cube.shortname), [
            'COMMAND OK',
            'STATE',
            'STATE',
            'You breathed light into a whole new exit'])

    await client.send('COMMAND go east', [
        'COMMAND OK',
        'STATE',
        'STATE',
        'STATE',
        'You materialize'])

    assert vil.player_obj in cube.contains
    assert vil.player_obj not in sanctum.contains

    await client.send('COMMAND go west', [
        'COMMAND OK',
        'STATE',
        'STATE',
        'STATE',
        'You materialize'])

    assert vil.player_obj not in cube.contains
    assert vil.player_obj in sanctum.contains


# TODO the following inventory tests should really be in their own file. in general
# this file has become a giant monster and needs serious help; either with
# splitting up into smaller files or helpers that reduce some of the async recv
# redundancy

@pytest.mark.asyncio
async def test_handle_get(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    foyer = GameObject.get(GameObject.shortname == 'god/foyer')

    cigar = GameObject.create_scripted_object(
        vil, 'vilmibm/a-fresh-cigar', 'item', dict(
            name='A fresh cigar',
            description='smoke it if you want'))

    GameWorld.put_into(foyer, cigar)

    await client.send('COMMAND get cigar', [
        'STATE',
        'STATE',
        'COMMAND OK',
        'STATE',
        'You grab A fresh cigar'])

    assert 'A fresh cigar' in [o.name for o in vil.player_obj.contains]


@pytest.mark.asyncio
async def test_handle_get_denied(client):
    god = UserAccount.get(UserAccount.username=='god')
    foyer = GameObject.get(GameObject.shortname=='god/foyer')
    phaser = GameObject.create_scripted_object(
        god, 'phaser-god', 'item', dict(
            name='a phaser',
            description='watch where u point it'))

    phaser.set_perm('carry', 'owner')

    GameWorld.put_into(foyer, phaser)

    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')

    await client.send('COMMAND get phaser', [
        '{red}You grab a hold of a phaser but no matter how hard you pull it stays rooted in place.'])


@pytest.mark.asyncio
async def test_handle_drop(client):
    god = UserAccount.get(UserAccount.username=='god')
    foyer = GameObject.get(GameObject.shortname=='god/foyer')
    phaser = GameObject.create_scripted_object(
        god, 'phaser-god', 'item', dict(
            name='a phaser',
            description='watch where u point it'))

    GameWorld.put_into(foyer, phaser)

    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')

    await client.send('COMMAND get phaser', [
        'COMMAND OK',
        'STATE',
        'You grab a phaser.'])

    await client.send('COMMAND drop phaser', [
        'COMMAND OK',
        'STATE',
        'STATE',
        'You drop a phaser'])

    assert 'a phaser' not in [o.name for o in vil.player_obj.contains]


@pytest.mark.asyncio
async def test_handle_put(client):
    god = UserAccount.get(UserAccount.username=='god')
    foyer = GameObject.get(GameObject.shortname=='god/foyer')
    phaser = GameObject.create_scripted_object(
        god, 'phaser-god', 'item', dict(
            name='a phaser',
            description='watch where u point it'))
    space_chest = GameObject.create_scripted_object(
        god, 'space-chest-god', 'item', dict(
            name='Fancy Space Chest',
            description="It's like a fantasy chest but palette swapped."))

    phaser.set_perm('carry', 'world')
    space_chest.set_perm('execute', 'world')

    GameWorld.put_into(foyer, phaser)
    GameWorld.put_into(foyer, space_chest)

    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')

    await client.send('COMMAND put phaser in chest', [
        'COMMAND OK',
        'You put a phaser in Fancy Space Chest'])


@pytest.mark.asyncio
async def test_handle_remove(client):
    god = UserAccount.get(UserAccount.username=='god')
    foyer = GameObject.get(GameObject.shortname=='god/foyer')
    phaser = GameObject.create_scripted_object(
        god, 'phaser-god', 'item', dict(
            name='a phaser',
            description='watch where u point it'))
    space_chest = GameObject.create_scripted_object(
        god, 'space-chest-god', 'item', dict(
            name='Fancy Space Chest',
            description="It's like a fantasy chest but palette swapped."))

    phaser.set_perm('carry', 'world')
    space_chest.set_perm('execute', 'world')

    GameWorld.put_into(foyer, space_chest)
    GameWorld.put_into(space_chest, phaser)

    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')

    await client.send('COMMAND remove phaser from chest', [
        'COMMAND OK',
        'STATE',
        'You remove a phaser from Fancy Space Chest and carry it with you.'])


@pytest.mark.asyncio
async def test_create_twoway_exit_via_world_perms(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    vil = UserAccount.get(UserAccount.username=='vilmibm')
    foyer = GameObject.get(GameObject.shortname=='god/foyer')
    foyer.set_perm('write', 'world')

    await client.send('COMMAND create room "Crystal Cube" a cube-shaped room made entirely of crystal.', [
        'COMMAND OK',
        'You breathed light into a whole new room'])

    cube = GameObject.get(GameObject.shortname.startswith('vilmibm/crystal-cube'))

    await client.send(
        'COMMAND create exit "Rusty Door" east {} A rusted, metal door'.format(cube.shortname), [
            'COMMAND OK',
            'STATE',
            'STATE',
            'You breathed light into a whole new exit'])

    await client.send('COMMAND go east', [
        'COMMAND OK',
        'STATE',
        'STATE',
        'STATE',
        'You materialize'])

    assert vil.player_obj in cube.contains
    assert vil.player_obj not in foyer.contains

    await client.send('COMMAND go west', [
        'COMMAND OK',
        'STATE',
        'STATE',
        'STATE',
        'You materialize'])

    assert vil.player_obj not in cube.contains
    assert vil.player_obj in foyer.contains


@pytest.mark.asyncio
async def test_revision(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')

    await client.send('COMMAND create item "A fresh cigar" An untouched black and mild with a wood tip', [
        'COMMAND OK',
        'STATE',
        'You breathed light into a whole new item. Its true name is vilmibm/a-fresh-cigar'
    ])

    cigar = GameObject.get(GameObject.shortname=='vilmibm/a-fresh-cigar')

    # TODO i left out the closing " on the description field and the witch
    # still compiled -- it resulted in None. very weird. need better checking
    # on code quality.
    new_code = """
    (witch "cigar"
      (has {"name" "A fresh cigar"
            "description" "An untouched black and mild with a wood tip"
            "smoked" False})
      (hears "smoke"
        (says "i'm cancer")))""".rstrip().lstrip()

    revision_payload = dict(
        shortname='vilmibm/a-fresh-cigar',
        code=new_code,
        current_rev=cigar.script_revision.id)

    await client.send('REVISION {}'.format(json.dumps(revision_payload)))

    msg = await client.assert_recv('OBJECT')
    payload = json.loads(msg.split(' ', maxsplit=1)[1])

    latest_rev = cigar.latest_script_rev

    assert payload == dict(
        shortname='vilmibm/a-fresh-cigar',
        data=dict(
            name='A fresh cigar',
            description='An untouched black and mild with a wood tip',
            smoked=False),
        permissions=dict(
            read='world',
            write='owner',
            carry='world',
            execute='world'),
        errors=[],
        code=new_code,
        current_rev=latest_rev.id)

    await client.send('COMMAND smoke', ['COMMAND OK',  "A fresh cigar says, \"i'm cancer\""])


@pytest.mark.asyncio
async def test_edit(event_loop):
    async with Client(event_loop) as vclient, Client(event_loop) as sclient:
        vil = await vclient.setup_user('vilmibm')
        await vclient.assert_next('STATE', 'STATE')
        snoozy = await sclient.setup_user('snoozy')
        await sclient.assert_next('STATE', 'STATE')

        await vclient.assert_next('STATE', 'STATE', 'snoozy fades')

        # create obj for vil
        await vclient.send('COMMAND create item "A fresh cigar" An untouched black and mild with a wood tip', [
            'COMMAND OK',
            'STATE',
            'You breathed light into a whole new item. Its true name is vilmibm/a-fresh-cigar'])

        # create obj for snoozy
        await sclient.send('COMMAND create item "A stick" Seems to be maple.', [
            'COMMAND OK',
            'STATE',
            'You breathed light into a whole new item. Its true name is snoozy/a-stick'])
        await sclient.send('COMMAND drop stick', [
            'COMMAND OK',
            'STATE',
            'STATE',
            'You drop A stick.'])

        # obj not found
        await vclient.send('COMMAND edit fart', [
            'STATE',
            'STATE',
            '{red}You look in vain for fart.{/}'])

        # perm denied
        await vclient.send('COMMAND edit stick', [
            '{red}You lack the authority to edit A stick{/}'])

        # success
        await vclient.send('COMMAND edit cigar', ['COMMAND OK'])
        msg = await vclient.assert_recv('OBJECT')
        cigar = GameObject.get(GameObject.shortname=='vilmibm/a-fresh-cigar')
        payload = json.loads(msg.split(' ', maxsplit=1)[1])
        assert payload == dict(
            edit=True,
            shortname=cigar.shortname,
            data=cigar.data,
            permissions=cigar.perms.as_dict(),
            code=cigar.script_revision.code,
            current_rev=cigar.script_revision.id)

        # already being edited
        await vclient.send('COMMAND edit cigar', [
            '{red}That object is already being edited{/}'])

        assert 1 == Editing.select().where(Editing.user_account==vil).count()
        assert 1 == Editing.select().where(Editing.game_obj==cigar).count()

        # success on snoozy's obj, ensuring we clear out first lock
        stick = GameObject.get(GameObject.shortname=='snoozy/a-stick')
        stick.set_perm('write', 'world')
        await vclient.send('COMMAND edit snoozy/a-stick', ['COMMAND OK'])
        msg = await vclient.assert_recv('OBJECT')
        assert 'a-stick' in msg

        assert 1 == Editing.select().where(Editing.user_account==vil).count()
        assert 0 == Editing.select().where(Editing.game_obj==cigar).count()
        assert 1 == Editing.select().where(Editing.game_obj==stick).count()

        revision_payload = dict(
            shortname='snoozy/a-stick',
            code=stick.script_revision.code,
            current_rev=stick.script_revision.id)

        await vclient.send('REVISION {}'.format(json.dumps(revision_payload)), ['OBJECT'])
        assert 0 == Editing.select().where(Editing.game_obj==stick).count()

# TODO witch exception when saving revision

@pytest.mark.asyncio
async def test_transitive_command(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')

    ### create an object to send transitive commands to
    await client.send('COMMAND create item "lemongrab" a high strung lemon man', [
        'COMMAND OK',
        'STATE',
        'You breathed light into a whole new item. Its true name is vilmibm/lemongrab'])

    lemongrab = GameObject.get(GameObject.shortname=='vilmibm/lemongrab')

    new_code = """
    (witch "lemongrab"
      (has {"name" "lemongrab"
            "description" "a high strung lemon man"})
      (hears "touch"
        (says "UNACCEPTABLE")))""".rstrip().lstrip()

    revision_payload = dict(
        shortname='vilmibm/lemongrab',
        code=new_code,
        current_rev=lemongrab.script_revision.id)

    await client.send('REVISION {}'.format(json.dumps(revision_payload)), ['OBJECT'])

    ### create an object for accepting whatever commands
    await client.send('COMMAND create item "cat" it is a cat', [
        'COMMAND OK',
        'STATE',
        'You breathed light into a whole new item. Its true name is vilmibm/cat'])

    cat = GameObject.get(GameObject.shortname=='vilmibm/cat')

    new_code = """
    (witch "cat"
      (has {"name" "cat"
            "description" "it is a cat"})
      (hears "touch"
        (says "purr")))""".rstrip().lstrip()

    revision_payload = dict(
        shortname='vilmibm/cat',
        code=new_code,
        current_rev=cat.script_revision.id)

    await client.send('REVISION {}'.format(json.dumps(revision_payload)), ['OBJECT'])

    # ensure non-transitive works
    await client.send('COMMAND touch', ['COMMAND OK'])
    await client.assert_set({'cat says, "purr"', 'lemongrab says, "UNACCEPTABLE"'})

    # target found
    await client.send('COMMAND touch lemongrab', ['COMMAND OK', 'lemongrab says, "UNACCEPTABLE"'])

    # TODO support for transitive-only commands

    # target not found
    await client.send('COMMAND touch contrivance', ['COMMAND OK'])
    await client.assert_set({'cat says, "purr"', 'lemongrab says, "UNACCEPTABLE"'})


@pytest.mark.asyncio
async def test_session_handling(event_loop):
    cube = None
    vil = None
    endo = None

    async with Client(event_loop) as eclient:
        endo = await eclient.setup_user('endo')
        await eclient.assert_next('STATE', 'STATE')
        async with Client(event_loop) as vclient:
            vil = await vclient.setup_user('vilmibm')
            await vclient.assert_next('STATE', 'STATE')
            await eclient.assert_next('STATE', 'STATE', 'vilmibm fades in')
            assert LastSeen.get_or_none(LastSeen.user_account==vil) is None
            assert vil.id in GameWorld._sessions
            await vclient.send('COMMAND create room "Crystal Cube" A cube-shaped room made entirely of crystal.', [
                'COMMAND OK',
                'You breathed light into a whole new room'])
            cube = GameObject.get(GameObject.shortname.startswith('vilmibm/crystal-cube'))
            GameWorld.put_into(cube, vil.player_obj)
            GameWorld.put_into(cube, endo.player_obj)
            await vclient.quit_game()

        await eclient.assert_next('STATE', 'STATE', 'STATE', 'STATE', 'vilmibm fades out')
        assert vil.player_obj not in cube.contains
        assert vil not in GameWorld._sessions
        ls = LastSeen.get_or_none(LastSeen.user_account==vil)
        assert ls.room.name == cube.name

        async with Client(event_loop) as vclient:
            await vclient.login('vilmibm')
            await eclient.assert_next('STATE', 'STATE', 'vilmibm fades in')
            assert vil.player_obj in cube.contains
            assert LastSeen.get_or_none(LastSeen.user_account==vil) is None

@pytest.mark.asyncio
async def test_witch_argument_string(client):
    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')
    echo_code = """
    (witch "Cave Echo"
      (has {"name" "Cave Echo"
            "description" "A creepy echo from the back of this cave"})
      (hears "say"
        (unless from-me?
          (says (+ arg " but spookily")))))
    """.rstrip().lstrip()
    await client.send('COMMAND create item "Cave Echo" A creepy echo from the back of this cave',
                      ['COMMAND OK', 'STATE', 'You breathed'])
    echo = GameObject.get(GameObject.shortname=='vilmibm/cave-echo')

    revision_payload = dict(
        shortname='vilmibm/cave-echo',
        code=echo_code,
        current_rev=echo.script_revision.id)

    await client.send('REVISION {}'.format(json.dumps(revision_payload)), ['OBJECT'])
    await client.send('COMMAND say hello there how are you')
    await client.assert_set({'COMMAND OK',
                             'vilmibm says, "hello there how are you"',
                             'Cave Echo says, "hello there how are you but spookily"'})

@pytest.mark.asyncio
async def test_witch_arguments_split(client):
    await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')

    vending_code = """
    (witch "Vending Machine"
      (has {"name" "Vending Machine"
            "description" "A Japanese-style vending machine."})
      (hears "give"
        (if (= "yen" (get args 1))
          (if (<= 100 (int (get args 0)))
            (says "have a pocari sweat. enjoy.")
            (says "need more yen"))
          (says "i only take yen sorry"))))
    """.lstrip().rstrip()

    await client.send('COMMAND create item "Vending Machine" A Japanese-style vending machine',
                      ['COMMAND OK', 'STATE', 'You breathed'])
    vending_machine = GameObject.get(GameObject.shortname=='vilmibm/vending-machine')

    revision_payload = dict(
        shortname='vilmibm/vending-machine',
        code=vending_code,
        current_rev=vending_machine.script_revision.id)

    await client.send('REVISION {}'.format(json.dumps(revision_payload)), ['OBJECT'])
    await client.send('COMMAND give machine 100 dollars', ['COMMAND OK'])
    await client.assert_next('Vending Machine says, "i only take yen sorry"')
    await client.send('COMMAND give machine 99 yen', ['COMMAND OK'])
    await client.assert_next('Vending Machine says, "need more yen"')
    await client.send('COMMAND give machine 100 yen', ['COMMAND OK'])
    await client.assert_next('Vending Machine says, "have a pocari sweat. enjoy."')


@pytest.mark.asyncio
async def test_teleport(client):
    vil = await client.setup_user('vilmibm')
    await client.assert_next('STATE', 'STATE')

    await client.send('COMMAND home', ['COMMAND OK', 'STATE', 'STATE', 'STATE', 'You materialize'])
    assert vil.player_obj.room.shortname == 'vilmibm/sanctum'

    await client.send('COMMAND foyer', ['COMMAND OK', 'STATE', 'STATE', 'STATE', 'You materialize'])
    assert vil.player_obj.room.shortname == 'god/foyer'


@pytest.mark.asyncio
async def test_handle_mode(event_loop):
    async with Client(event_loop) as vclient, Client(event_loop) as eclient:
        vil = await vclient.setup_user('vilmibm')
        await vclient.assert_next('STATE', 'STATE')
        endo = await eclient.setup_user('endo')
        await eclient.assert_next('STATE', 'STATE')

        await vclient.assert_next('STATE', 'STATE', 'endo fades')

        await vclient.send('COMMAND create item "cat" it is a cat', [
            'COMMAND OK',
            'STATE',
            'You breathed light into a whole new item. Its true name is vilmibm/cat'])

        await vclient.send('COMMAND mode cat carry owner', [
            'COMMAND OK',
            'The world seems to gently vibrate around you. You have updated the carry permission to owner.'])

        cat = GameObject.get(GameObject.shortname=='vilmibm/cat')
        assert cat.perms.carry == Permission.OWNER

        await vclient.send('COMMAND drop cat')

        await eclient.send('COMMAND mode cat carry world', [
            '{red}you lack the authority to mess'])

