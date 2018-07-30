from unittest.mock import Mock
from ..migrations import reset_db
from ..models import GameObject
from ..world import GameWorld
from ..mapping import from_room
from .tm_test_case import TildemushUnitTestCase

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

    def test_from_room_bad_distance(self):
        with self.assertRaisesRegex(ValueError, 'greater than 0'):
            from_room(self.foyer, -1)

    def test_from_room_max_distance(self):
        mapfile = from_room(self.foyer, 100)
        expected = 'TODO'
        assert expected == mapfile

    def test_from_room_zero_distance(self):
        pass

    def test_from_room_mid_distance(self):
        pass
