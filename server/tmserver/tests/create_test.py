# TODO unit tests for create command parsing

from ..errors import ClientException
from ..models import UserAccount, GameObject
from ..world import GameWorld
from .tm_test_case import TildemushTestCase

class DeriveShortnameTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')

    def test_no_args(self):
        # This is a weird case that probably won't come up. since we are
        # passing no strings, we end up with a shortname of just the author
        # name. naturally the DB already has a game object with that name, so
        # we end up with 1. Nothing's really wrong, but it's an accidental test
        # of the dupe case.
        result = GameWorld.derive_shortname(self.vil.player_obj)
        assert result == 'vilmibm-1'

    def test_one_string(self):
        result = GameWorld.derive_shortname(self.vil.player_obj, 'foot')
        assert result == 'foot-vilmibm'

    def test_many_strings(self):
        result = GameWorld.derive_shortname(self.vil.player_obj, 'foot', 'toe', 'whatever')
        assert result == 'foot-toe-whatever-vilmibm'

    def test_dupes(self):
        GameObject.create(
            author=self.vil,
            name='whatever',
            shortname='foot-vilmibm')
        for x in range(0,10):
            GameObject.create(
                author=self.vil,
                name='whatever',
                shortname='foot-vilmibm-{}'.format(x))
        result = GameWorld.derive_shortname(self.vil.player_obj, 'foot')
        assert result == 'foot-vilmibm-12'

class ParseCreateCommandTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')

    def test_malformed_create(self):
        malformed = (
            'item lol',
            'item',
            'item a very pretty name a fine description',
            '',
            'item "hmm"',
            'item "forgetting to close oops')

        for bad in malformed:
            with self.assertRaisesRegex(
                    ClientException,
                    'malformed call to /create'):
                GameWorld.parse_create(bad)

    def test_bad_object_type(self):
        with self.assertRaisesRegex(
                ClientException,
                'Unknown type for /create'):
            GameWorld.parse_create('fart "Yeah" sorry')
