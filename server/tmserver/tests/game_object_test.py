from unittest import mock
from ..models import UserAccount, GameObject, Contains
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

