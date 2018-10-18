from unittest import mock
from .. import models
from ..errors import WitchError
from ..models import UserAccount, GameObject, Contains, Script, ScriptRevision, Permission
from ..scripting import ScriptEngine
from ..world import GameWorld

from .tm_test_case import TildemushTestCase

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

    def test_ensure_data_ignores_empty_mapping(self):
        with mock.patch('tmserver.models.GameObject.save') as save_m:
            self.snoozy._ensure_data({})

        assert not save_m.called

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

    def test_handles_new_default_keys(self):
        some_data = {
            'smoked': False,
            'length': 4
        }
        self.snoozy._ensure_data(some_data)
        assert False == self.snoozy.get_data('smoked')
        assert 4 == self.snoozy.get_data('length')
        new_data = {
            'smoked': True,
            'length': 20,
            'wrapper': 'brown',
        }
        self.snoozy._ensure_data(new_data)
        assert False == self.snoozy.get_data('smoked')
        assert 4 == self.snoozy.get_data('length')
        assert 'brown' == self.snoozy.get_data('wrapper')


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

        self.script = Script.create(
            name='horse',
            author=vil_ua
        )

        self.script_rev = ScriptRevision.create(
            script=self.script,
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
              (provides "pet"
                (set-data "num-pets" (+ 1 (get-data "num-pets")))
                  (if (= 0 (% (get-data "num-pets") 5))
                    (says "neigh neigh neigh i am horse"))))''')

        self.snoozy = GameObject.create(
            author=vil_ua,
            shortname='snoozy',
            script_revision=self.script_rev)

    def test_no_script_revision(self):
        result = self.vil.handle_action(GameWorld, self.snoozy, 'kick', '')
        assert result is None

    def test_engine_is_created(self):
        eng = self.snoozy.engine
        assert isinstance(eng, ScriptEngine)

    def test_sets_permissions(self):
        self.snoozy.init_scripting()
        for p in ['read', 'write', 'carry', 'execute']:
            self.assertEqual(getattr(self.snoozy.perms, p), Permission.WORLD)

    def test_creates_hear_handler(self):
        self.assertIsNotNone(self.snoozy.engine.hears.get("*sit*"))

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
        assert result == '{} <- {} with foobar'.format(self.snoozy, self.vil)

    def test_bad_witch(self):
        self.script_rev.code = '''(some garbage)'''
        self.script_rev.save()
        with self.assertRaises(WitchError):
            self.snoozy.handle_action(GameWorld, self.vil, 'pet', '')

    def test_unhandled_action(self):
        assert None == self.snoozy.handle_action(GameWorld, self.vil, 'poke', '')
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
            assert SIGIL == self.snoozy._engine.handler(None, self.snoozy, 'give', arg_str)

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
            assert ScriptEngine.noop == self.snoozy._engine.handler(None, self.snoozy, 'give', arg_str), arg_str
