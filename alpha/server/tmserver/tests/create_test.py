# TODO unit tests for create command parsing

from ..errors import UserError
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
        result = GameWorld.derive_shortname(self.vil.player_obj)
        assert result == 'vilmibm/object'
        GameObject.create(
            author=self.vil,
            shortname='vilmibm/object')
        result = GameWorld.derive_shortname(self.vil.player_obj)
        assert result == 'vilmibm/object-3'

    def test_one_string(self):
        result = GameWorld.derive_shortname(self.vil.player_obj, 'foot')
        assert result == 'vilmibm/foot'

    def test_many_strings(self):
        result = GameWorld.derive_shortname(self.vil.player_obj, 'foot', 'toe', 'whatever')
        assert result == 'vilmibm/foot-toe-whatever'

    def test_dupes(self):
        GameObject.create(
            author=self.vil,
            shortname='vilmibm/foot')
        for x in range(0,10):
            GameObject.create(
                author=self.vil,
                shortname='vilmibm/foot-{}'.format(x))
        result = GameWorld.derive_shortname(self.vil.player_obj, 'foot')
        assert result == 'vilmibm/foot-13'

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
                    UserError,
                    'try /create'):
                GameWorld.parse_create(bad)

    def test_bad_object_type(self):
        with self.assertRaisesRegex(
                UserError,
                'Unknown type for /create'):
            GameWorld.parse_create('fart "Yeah" sorry')
