from unittest import mock

from .tm_test_case import TildemushTestCase
from ..errors import ClientException
from ..models import UserAccount, GameObject
from ..world import GameWorld

def setup_scene():
    foyer = GameObject.get(GameObject.shortname=='foyer')
    god = UserAccount.get(UserAccount.username=='god')

    vil_ua = UserAccount.create(
        username='vilmibm',
        password='foobarbazquux')

    can = GameObject.create_scripted_object(
        'item', god, 'can-god', dict(
            name='A Rusted Tin Can',
            description='The label has been torn off. A patch of adhesive is still a little sticky, though the metal is all rusted over. Something about it is unsettling.'))
    bag = GameObject.create_scripted_object(
        'item', god, 'bag-god', dict(
            name='A Garbage Bag',
            description="It's just a garbage bag. The black, glossy kind. You wonder how much stuff you could fit in there."))

    # TODO initial perms? by default, things are pretty open. i'll restrict as
    # needed unless that sucks...
    GameWorld.put_into(foyer, can)
    GameWorld.put_into(foyer, bag)
    GameWorld.put_into(foyer, vil_ua.player_obj)

    return vil_ua.player_obj

@mock.patch('tmserver.world.GameWorld.user_hears')
class GetTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = setup_scene()

    def test_obj_not_found(self, _):
        with self.assertRaisesRegex(
                ClientException,
                'You look in vain for shoe.'):
            GameWorld.handle_get(self.vil, 'shoe')

    def test_obj_denied(self, _):
        pass

    def test_success(self, _):
        pass

    def test_ambiguity(self, _):
        pass


class DropTest(TildemushTestCase):
    def test_obj_not_found(self):
        pass

    def test_success(self):
        pass

    def test_ambiguity(self):
        pass

class PutTest(TildemushTestCase):
    def test_malformed(self):
        pass

    def test_target_not_found(self):
        pass

    def test_target_in_inv(self):
        pass

    def test_target_in_room(self):
        pass

    def test_container_in_inv(self):
        pass

    def test_container_in_room(self):
        pass

    def test_container_not_found(self):
        pass

    def test_target_denied(self):
        pass

    def test_container_denied(self):
        pass

class RemoveTest(TildemushTestCase):
    def test_malformed(self):
        pass

    def test_target_not_found(self):
        pass

    def test_target_in_inv(self):
        pass

    def test_target_in_room(self):
        pass

    def test_container_in_inv(self):
        pass

    def test_container_in_room(self):
        pass

    def test_container_not_found(self):
        pass

    def test_target_denied(self):
        pass

    def test_container_denied(self):
        pass
