from unittest import mock

from .tm_test_case import TildemushTestCase
from ..errors import ClientException
from ..models import UserAccount, GameObject, Permission
from ..world import GameWorld

class InventoryTestCase(TildemushTestCase):
    def setUp(self):
        super().setUp()
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

        self.foyer = foyer
        self.god = god
        self.vil = vil_ua.player_obj
        self.bag = bag
        self.can = can

@mock.patch('tmserver.world.GameWorld.user_hears')
class GetTest(InventoryTestCase):
    def test_obj_not_found(self, _):
        with self.assertRaisesRegex(
                ClientException,
                'You look in vain for shoe.'):
            GameWorld.handle_get(self.vil, 'shoe')

    def test_obj_denied(self, _):
        self.can.perms.carry = Permission.OWNER
        self.can.perms.save()

        with self.assertRaisesRegex(
                ClientException,
                'You grab a hold of A Rusted Tin Can but'):
            GameWorld.handle_get(self.vil, 'can')

    def test_success(self, mock_hears):
        GameWorld.handle_get(self.vil, 'can')
        assert self.can in self.vil.contains
        assert mock_hears.called

    def test_ambiguity(self, mock_hears):
        shiny_can = GameObject.create_scripted_object(
            'item', self.god, 'can-shiny-god', dict(
                name='A New, Shiny Tin Can',
                description="A new can. Not even adhesive on this. You can see yourself in its reflection but you're all ripply."))
        GameWorld.put_into(self.foyer, shiny_can)
        assert shiny_can in self.foyer.contains
        assert self.can in self.foyer.contains
        assert shiny_can.fuzzy_match('can')
        assert self.can.fuzzy_match('can')
        GameWorld.handle_get(self.vil, 'can')
        assert self.can in self.vil.contains
        assert shiny_can not in self.vil.contains
        assert mock_hears.called


class DropTest(InventoryTestCase):
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
