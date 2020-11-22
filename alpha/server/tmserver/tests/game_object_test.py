from unittest import mock
from .. import models
from ..errors import WitchError
from ..models import UserAccount, GameObject, Contains, Script, ScriptRevision, Permission
from ..scripting import ScriptEngine, random_number
from ..world import GameWorld

from .tm_test_case import TildemushTestCase, TildemushUnitTestCase

class FuzzyMatchTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')

        self.phaser = GameObject.create_scripted_object(
            self.vil, 'phaser-vilmibm-666', 'item', dict(
                name='Federation Phaser',
                description='Looks like a remote control, but is far deadlier. You should probably leave it set for stun.'))

    def test_ignores_color_codes(self):
        rainbow = GameObject.create_scripted_object(
            self.vil, 'contrived-example-vilmibm', 'item', dict(
                name='a {red}r{orange}a{yellow}i{green}n{blue}b{indigo}o{violet}w{/}',
                description="all the way across the sky."))
        assert rainbow.fuzzy_match('rainbow')

    def test_exact_name_match(self):
        assert self.phaser.fuzzy_match('Federation Phaser')
        assert self.phaser.fuzzy_match('federation phaser')

    def test_exact_shortname_match(self):
        assert self.phaser.fuzzy_match('phaser-vilmibm-666')
        assert self.phaser.fuzzy_match('pHaSeR-ViLmIbM-666')

    def test_fuzzy_name_match(self):
        assert self.phaser.fuzzy_match('federation')
        assert self.phaser.fuzzy_match('Federation')

    def test_fuzzy_shortname_match(self):
        assert self.phaser.fuzzy_match('phaser-vil')
        assert self.phaser.fuzzy_match('pHasEr-vIl')

    def test_substr_name_match(self):
        # yeah this is contrived sorry
        assert self.phaser.fuzzy_match('ederation phase')
        assert self.phaser.fuzzy_match('edErAtIoN pHase')

    def test_substr_shortname_match(self):
        assert self.phaser.fuzzy_match('ser-vil')
        assert self.phaser.fuzzy_match('sEr-vIl')


class CreateScriptedObjectTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')

    def test_data_initialized(self):
        banana = GameObject.create_scripted_object(
            self.vil, 'banana-vilmibm', 'item', dict(
                name='A Banana',
                description='Still green.'))
        assert banana.data == dict(
            name='A Banana',
            description='Still green.')

class GameObjectDataTest(TildemushTestCase):
    """This test merely ensures the ensure, get, and set data stuff works okay.
    Scripts aren't involved."""
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')
        self.snoozy = GameObject.create(
            author=self.vil,
            shortname='snoozy')

    def test_data_default(self):
        assert {} == GameObject.get_by_id(self.snoozy.id).data

    def test_ensure_data(self):
        some_data = {
            'stuff': 'here',
            'aw': 'yis',
        }
        self.snoozy._ensure_data(some_data)
        assert some_data == GameObject.get_by_id(self.snoozy.id).data

    def test_set_data(self):
        some_data = {
            'num_pets': 0,
            'aw': 'yis',
        }
        self.snoozy._ensure_data(some_data)
        self.snoozy.set_data('num_pets', 1)
        assert 1 == GameObject.get_by_id(self.snoozy.id).data['num_pets']

    def test_get_data(self):
        some_data = {
            'num_pets': 0,
            'aw': 'yis',
        }
        self.snoozy._ensure_data(some_data)
        self.snoozy.set_data('num_pets', self.snoozy.get_data('num_pets') + 1)
        assert 1 == GameObject.get_by_id(self.snoozy.id).get_data('num_pets')


class GameObjectComparisonTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')
        self.snoozy = GameObject.create_scripted_object(
            author=self.vil,
            shortname='snoozy',
            format_dict=dict(
                name='snoozy',
                description='a horse'))

    def test_str_representation(self):
        assert 'GameObject<snoozy>'.format(self.vil) == repr(self.snoozy)
        assert 'snoozy'.format(self.vil) == str(self.snoozy)

    def test_eq_operations(self):
        snoozy = GameObject.get_by_id(self.snoozy.id)
        assert snoozy == self.snoozy
        snoozy.shortname =  'lol'
        assert snoozy != self.snoozy

    def test_hash_operations(self):
        snoozy = GameObject.get_by_id(self.snoozy.id)
        assert snoozy.__hash__() == self.snoozy.__hash__()
        snoozy.shortname =  'lol'

        assert snoozy.__hash__() != self.snoozy.__hash__()


class GameObjectScriptEngineTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        vil_ua = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')
        self.vil = vil_ua.player_obj

        self.snoozy = GameObject.create_scripted_object(
                vil_ua, 'vilmibm/snoozy', 'item', {
                    'name': 'snoozy',
                    'description': 'a horse'})

        script_rev = ScriptRevision.create(
            script=self.snoozy.script_revision.script,
            code='''
            (incantation by vilmibm
              (has {"num-pets" 0
                    "name" "snoozy"
                    "description" "a horse"})
              (allows {
                 "read" "world"
                 "write" "world"
                 "carry" "world"
                 "execute" "world"})
              (hears "*sit*" (does "stamps at the ground"))
              (sees "*extends hand*" (does "extends hoof"))
              (provides "pet"
                (set-data "num-pets" (+ 1 (get-data "num-pets")))
                  (if (= 0 (% (get-data "num-pets") 5))
                    (says "neigh neigh neigh i am horse"))))''')
        self.snoozy.script_revision = script_rev
        self.snoozy.save()
        self.snoozy.init_scripting(use_db_data=False)

    def test_no_script_revision(self):
        result = self.vil.handle_action(GameWorld, self.snoozy, 'kick', '')
        assert result == (False, None)

    def test_engine_is_created(self):
        eng = self.snoozy.engine
        assert isinstance(eng, ScriptEngine)

    def test_sets_permissions(self):
        self.snoozy.init_scripting()
        for p in ['read', 'write', 'carry', 'execute']:
            self.assertEqual(getattr(self.snoozy.perms, p), Permission.WORLD)

    def test_creates_hear_handler(self):
        self.assertIsNotNone(self.snoozy.engine.hears.get("*sit*"))

    def test_creates_see_handler(self):
        self.assertIsNotNone(self.snoozy.engine.sees.get("*extends hand*"))

    def test_handler_works(self):
        self.snoozy.handle_action(GameWorld, self.vil, 'pet', '')
        assert self.snoozy.get_data('num-pets') == 1
        self.snoozy.handle_action(GameWorld, self.vil, 'pet', '')
        self.snoozy.handle_action(GameWorld, self.vil, 'pet', '')
        self.snoozy.handle_action(GameWorld, self.vil, 'pet', '')
        with mock.patch('tmserver.models.GameObject.say') as mock_say:
            self.snoozy.handle_action(GameWorld, self.vil, 'pet', '')
            mock_say.assert_called_once_with('neigh neigh neigh i am horse')

    def test_debug_handler(self):
        result = self.snoozy.handle_action(GameWorld, self.vil, 'debug', 'foobar')
        assert result == (False, '{} <- {} with foobar'.format(self.snoozy, self.vil))

    def test_unhandled_action(self):
        assert (False, None) == self.snoozy.handle_action(GameWorld, self.vil, 'poke', '')
        with mock.patch('tmserver.scripting.ScriptEngine.noop') as mock_noop:
            self.snoozy.handle_action(GameWorld, self.vil, 'poke', [])
            assert mock_noop.called

    def test_transitive_matching(self):
        SIGIL = 'lol hi'
        self.snoozy._engine = ScriptEngine(self.snoozy)
        self.snoozy._engine.add_provides_handler('give hay to $this', SIGIL)

        should_match = [
            'hay to snoozy',
            'hay to "snoozy"',
            "hay to 'snoozy'",
            'hay to snoo'
        ]

        for arg_str in should_match:
            assert (True, SIGIL) == self.snoozy._engine.handler(None, self.snoozy, 'give', arg_str)

        should_not_match = [
            'hay to fred',
            'hay to someone',
            'hey to snoozy',
            'hai to snoozy',
            'hay to yzoons',
            'hay',
            'hay to'
        ]

        for arg_str in should_not_match:
            assert (False, ScriptEngine.noop) == self.snoozy._engine.handler(None, self.snoozy, 'give', arg_str), arg_str

class TestRandomNumber(TildemushUnitTestCase):
    def test_no_args(self):
        result = None
        for _ in range(100):
            result = random_number()
            assert result >= 1
            assert result <= 10

    def test_one_arg(self):
        result = None
        for _ in range(100):
            result = random_number(20)
            assert result >= 1
            assert result <= 20

    def test_two_args(self):
        result = None
        for _ in range(100):
            result = random_number(30, 60)
            assert result >= 30
            assert result <= 60

    def test_bad_range(self):
        result = None
        for _ in range(100):
            result = random_number(100, 90)
            assert result >= 90
            assert result <= 100
