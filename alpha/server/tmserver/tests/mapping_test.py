import sys

from unittest.mock import Mock
from ..migrations import reset_db
from ..models import GameObject
from ..world import GameWorld
from ..mapping import from_room, graph_easy
from .tm_test_case import TildemushUnitTestCase

import pytest

OSX = sys.platform == 'darwin'

RENDERED_MAP = '''                      ┌────────────────┐         ┌─────────────┐  north   ┌───────────┐  north   ┌───────────────────────┐
                      │ Small Bedroom  │         │   Kitchen   │ ───────> │ Rear Lawn │ ───────> │        Forest         │
                      └────────────────┘         └─────────────┘          └───────────┘          └───────────────────────┘
                        ∧                          ∧
                        │ south                    │ north
                        │                          │
┌──────────┐  north   ┌────────────────┐  west   ┌─────────────┐  above   ┌───────────┐  above   ┌───────────────────────┐  above   ┌───────────┐
│ Bathroom │ <─────── │    Hallway     │ <────── │             │ ───────> │ Airy Loft │ ───────> │         Attic         │ ───────> │ Tree Limb │
└──────────┘          └────────────────┘         │             │          └───────────┘          └───────────────────────┘          └───────────┘
                        │                        │             │
                        │ west                   │    Foyer    │
                        ∨                        │             │
                      ┌────────────────┐         │             │  below   ┌───────────┐  west    ┌───────────────────────┐
                      │ Master Bedroom │  ┌───── │             │ ───────> │ Basement  │ ───────> │     Computer Room     │
                      └────────────────┘  │      └─────────────┘          └───────────┘          └───────────────────────┘
                        │                 │        │                        │
                        │ west            │        │ south                  │ east
                        ∨                 │        ∨                        ∨
                      ┌────────────────┐  │ east ┌─────────────┐          ┌───────────┐
                      │   West Lawn    │  │      │ Front Lawn  │          │ Rec Room  │
                      └────────────────┘  │      └─────────────┘          └───────────┘
                                          │      ┌─────────────┐  east    ┌───────────┐  east    ┌───────────────────────┐
                                          └────> │ Living Room │ ───────> │ East Lawn │ ───────> │ Abandoned House Foyer │
                                                 └─────────────┘          └───────────┘          └───────────────────────┘
                                                   │
                                                   │ north
                                                   ∨
                                                 ┌─────────────┐
                                                 │ Dining Room │
                                                 └─────────────┘
'''

class TestMapping(TildemushUnitTestCase):
    @classmethod
    def tearDownClass(cls):
        GameWorld.user_hears = cls.hears

    @classmethod
    def setUpClass(cls):
        reset_db()
        cls.foyer = GameObject.get(GameObject.shortname=='god/foyer')
        cls.god = GameObject.get(GameObject.shortname=='god')

        cls.hears = GameWorld.user_hears
        GameWorld.user_hears = Mock()

        rooms = ['Basement',
                 'Airy Loft',
                 'Front Lawn',
                 'Kitchen',
                 'Rear Lawn',
                 'Forest',
                 'Attic',
                 'Tree Limb',
                 'Dining Room',
                 'Living Room',
                 'East Lawn',
                 'West Lawn',
                 'Bathroom',
                 'Small Bedroom',
                 'Master Bedroom',
                 'Rec Room',
                 'Computer Room',
                 'Hallway',
                 'Abandoned House Living Room',
                 'Abandoned House Kitchen',
                 'Abandoned House Foyer',
                 'Abandoned House Master Bedroom',
                 'Abandoned House Small Bedroom',
                 'Abandoned House Basement',
                 'Tunnel',
                 'Graveyard Cave',
                 'Graveyard',
                 'South Graveyard',
                 'North Graveyard',
                 'East Graveyard',
                 'West Graveyard',]

        for room in rooms:
            GameWorld.create_room(cls.god, room, '')

        exits = [
            ('Narrow stairs', 'foyer', 'below', 'basement'),
            ('Ladder', 'foyer', 'above', 'airy-loft'),
            ('Screen Door', 'foyer', 'south', 'front-lawn'),
            ('Door', 'foyer', 'north', 'kitchen'),
            ('Screen Door', 'kitchen', 'north', 'rear-lawn'),
            ('Path', 'rear-lawn', 'north', 'forest'),
            ('Hatch', 'airy-loft', 'above', 'attic'),
            ('Hole', 'attic', 'above', 'tree-limb'),
            ('Step', 'foyer', 'east', 'living-room'),
            ('Double Doors', 'living-room', 'north', 'dining-room'),
            ('Window', 'living-room', 'east', 'east-lawn'),
            ('Swinging Door', 'foyer', 'west', 'hallway'),
            ('Door', 'hallway', 'north', 'bathroom'),
            ('Door', 'hallway', 'south', 'small-bedroom'),
            ('Door', 'hallway', 'west', 'master-bedroom'),
            ('Window', 'master-bedroom', 'west', 'west-lawn'),
            ('Door', 'basement', 'west', 'computer-room'),
            ('Step', 'basement', 'east', 'rec-room'),
            ('Path', 'east-lawn', 'east', 'abandoned-house-foyer'),
            ('Old Door', 'abandoned-house-foyer', 'east', 'abandoned-house-kitchen'),
            ('Step', 'abandoned-house-foyer', 'north', 'abandoned-house-living-room'),
            ('Moldy Door', 'abandoned-house-foyer', 'south', 'abandoned-house-small-bedroom'),
            ('Spiral Staircase', 'abandoned-house-foyer', 'above', 'abandoned-house-master-bedroom'),
            ('Trap Door', 'abandoned-house-foyer', 'below', 'abandoned-house-basement'),
            ('Hole', 'abandoned-house-basement', 'east', 'tunnel'),
            ('Hole', 'tunnel', 'east', 'graveyard-cave'),
            ('Hatch', 'graveyard-cave', 'above', 'graveyard'),
            ('Path', 'graveyard', 'north', 'north-graveyard'),
            ('Path', 'graveyard', 'east', 'east-graveyard'),
            ('Path', 'graveyard', 'south', 'south-graveyard'),
            ('Path', 'graveyard', 'west', 'west-graveyard'),]

        for name, current, direction, target in exits:
            current_room = GameObject.get(GameObject.shortname=='god/'+current)
            GameWorld.put_into(current_room, cls.god)
            GameWorld.create_exit(
                cls.god, name,
                '{} god/{} TODO is desc optional?'.format(direction, target))

    @pytest.mark.skipif(OSX, reason="TODO boxgraph not compiled for OSX")
    def test_from_room_bad_distance(self):
        with self.assertRaisesRegex(ValueError, 'greater than 0'):
            from_room(GameWorld, self.foyer, -1)

    @pytest.mark.skipif(OSX, reason="TODO boxgraph not compiled for OSX")
    def test_from_room_max_distance(self):
        mapfile = from_room(GameWorld, self.foyer, 100)
        expected = '''
[ Foyer ] -- north --> [ Kitchen ]
[ Foyer ] -- below --> [ Basement ]
[ Foyer ] -- above --> [ Airy Loft ]
[ Foyer ] -- east --> [ Living Room ]
[ Foyer ] -- west --> [ Hallway ]
[ Foyer ] -- south --> [ Front Lawn ]
[ Kitchen ] -- north --> [ Rear Lawn ]
[ Rear Lawn ] -- north --> [ Forest ]
[ Basement ] -- east --> [ Rec Room ]
[ Basement ] -- west --> [ Computer Room ]
[ Airy Loft ] -- above --> [ Attic ]
[ Attic ] -- above --> [ Tree Limb ]
[ Living Room ] -- north --> [ Dining Room ]
[ Living Room ] -- east --> [ East Lawn ]
[ East Lawn ] -- east --> [ Abandoned House Foyer ]
[ Abandoned House Foyer ] -- north --> [ Abandoned House Living Room ]
[ Abandoned House Foyer ] -- below --> [ Abandoned House Basement ]
[ Abandoned House Foyer ] -- above --> [ Abandoned House Master Bedroom ]
[ Abandoned House Foyer ] -- east --> [ Abandoned House Kitchen ]
[ Abandoned House Foyer ] -- south --> [ Abandoned House Small Bedroom ]
[ Abandoned House Basement ] -- east --> [ Tunnel ]
[ Tunnel ] -- east --> [ Graveyard Cave ]
[ Graveyard Cave ] -- above --> [ Graveyard ]
[ Graveyard ] -- north --> [ North Graveyard ]
[ Graveyard ] -- east --> [ East Graveyard ]
[ Graveyard ] -- west --> [ West Graveyard ]
[ Graveyard ] -- south --> [ South Graveyard ]
[ Hallway ] -- north --> [ Bathroom ]
[ Hallway ] -- west --> [ Master Bedroom ]
[ Hallway ] -- south --> [ Small Bedroom ]
[ Master Bedroom ] -- west --> [ West Lawn ]'''.lstrip()
        assert sorted(expected.split('\n')) == sorted(mapfile.split('\n'))

    @pytest.mark.skipif(OSX, reason="TODO boxgraph not compiled for OSX")
    def test_from_room_zero_distance(self):
        mapfile = from_room(GameWorld, self.foyer, distance=0)
        expected = '''
[ Foyer ] -- north --> [ Kitchen ]
[ Foyer ] -- below --> [ Basement ]
[ Foyer ] -- above --> [ Airy Loft ]
[ Foyer ] -- east --> [ Living Room ]
[ Foyer ] -- west --> [ Hallway ]
[ Foyer ] -- south --> [ Front Lawn ]'''.lstrip()
        assert sorted(expected.split('\n')) == sorted(mapfile.split('\n'))

    @pytest.mark.skipif(OSX, reason="TODO boxgraph not compiled for OSX")
    def test_boxgraph(self):
        mapfile = from_room(GameWorld, self.foyer, distance=2)
        rendered = graph_easy(mapfile)
        assert rendered == RENDERED_MAP
