import types
from unittest import mock
from .. import models
from ..errors import WitchException
from ..models import UserAccount, GameObject, Contains, Script, ScriptRevision, ScriptEngine
from ..world import GameWorld

from .tm_test_case import TildemushTestCase

class GameObjectDataTest(TildemushTestCase):
    """This test merely ensures the ensure, get, and set data stuff works okay.
    Scripts aren't involved."""
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux',
            display_name='a gaseous cloud')
        self.snoozy = GameObject.create(
            author=self.vil,
            name='snoozy')

    def test_data_default(self):
        assert {} == GameObject.get_by_id(self.snoozy.id).data

    def test_ensure_data_ignores_empty_mapping(self):
        with mock.patch('tmserver.models.GameObject.save') as save_m:
            self.snoozy._ensure_data({})

        assert not save_m.called

    def test_ensure_data_ignores_populated_data_mapping(self):
        self.snoozy.data = {'stuff': 'here'}
        self.snoozy.save()
        with mock.patch('tmserver.models.GameObject.save') as save_m:
            self.snoozy._ensure_data({'aw':'yis'})
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


def GameObjectComparisonTest(self):

    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux',
            display_name='a gaseous cloud')
        self.snoozy = GameObject.create(
            author=self.vil,
            name='snoozy')

        self.horse_script = Script.create(author=self.vil)
        self.revision = ScriptRevision.create(code='<witch code>', script=self.horse_script)

    def test_str_representation(self):
        assert 'GameObject<snoozy> authored by {}'.format(self.vil) == str(self.snoozy)

    def test_eq_operations_without_revisions(self):
        snoozy = GameObject.get_by_id(self.snoozy.id)
        assert True == (snoozy == self.snoozy)

        snoozy.name = 'false snoozy'
        assert False == (snoozy == self.snoozy)

    def test_eq_operations(self):
        self.snoozy.script_revision = self.revision
        self.snoozy.save()
        snoozy = GameObject.get_by_id(self.snoozy.id)
        assert True == (snoozy == self.snoozy)

        revision = ScriptRevision.create(code='(witch)', script=self.snoozy.script)
        snoozy = GameObject.get_by_id(self.snoozy.id)
        snoozy.script_revision = revision
        assert True == (snoozy != self.snoozy)

    def test_hash_operations(self):
        self.snoozy.script_revision = self.revision
        self.snoozy.save()
        snoozy = GameObject.get_by_id(self.snoozy.id)
        assert True == (snoozy.__hash__() == self.snoozy.__hash__())

        revision = ScriptRevision.create(code='(witch)', script=self.snoozy.script)
        snoozy = GameObject.get_by_id(self.snoozy.id)
        snoozy.script_revision = revision
        assert False == (snoozy.__hash__() == self.snoozy.__hash__())


class GameObjectScriptEngineTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        vil_ua = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux',
            display_name='a gaseous cloud')
        self.vil = vil_ua.player_obj

        self.script = Script.create(
            name='horse',
            author=vil_ua
        )

        self.script_rev = ScriptRevision.create(
            script=self.script,
            code='''
            (witch "horse" by "vilmibm"
              (has {"num-pets" 0})
              (hears "pet"
                (set-data "num-pets" (+ 1 (get-data "num-pets")))
                  (if (= 0 (% (get-data "num-pets") 5))
                    (says "neigh neigh neigh i am horse"))))''')

        self.snoozy = GameObject.create(
            author=vil_ua,
            name='snoozy',
            script_revision=self.script_rev)

    def test_no_script_revision(self):
        result = self.vil.handle_action(self.snoozy, 'kick', [])
        assert result is None

    def test_witch_header_read(self):
        assert models.WITCH_HEADER is not None

    def test_engine_is_created(self):
        eng = self.snoozy.engine
        assert isinstance(eng, ScriptEngine)

    def test_handler_added(self):
        assert type(self.snoozy.engine.handler('pet')) == types.FunctionType

    def test_handler_works(self):
        self.snoozy.handle_action(self.vil, 'pet', [])
        assert self.snoozy.get_data('num-pets') == 1
        self.snoozy.handle_action(self.vil, 'pet', [])
        self.snoozy.handle_action(self.vil, 'pet', [])
        self.snoozy.handle_action(self.vil, 'pet', [])
        with mock.patch('tmserver.models.GameObject.say') as mock_say:
            self.snoozy.handle_action(self.vil, 'pet', [])
            mock_say.assert_called_once_with('neigh neigh neigh i am horse')

    def test_debug_handler(self):
        result = self.snoozy.handle_action(self.vil, 'debug', [])
        assert result == '{} <- {} with []'.format(self.snoozy, self.vil)

    def test_bad_witch(self):
        self.script_rev.code = '''(witch oops lol haha)'''
        self.script_rev.save()
        with self.assertRaises(WitchException):
            self.snoozy.handle_action(self.vil, 'pet', [])

    def test_unhandled_action(self):
        assert None == self.snoozy.handle_action('poke', self.vil, [])
        with mock.patch('tmserver.models.ScriptEngine.noop') as mock_noop:
            self.snoozy.handle_action('poke', self.vil, [])
            assert mock_noop.called


