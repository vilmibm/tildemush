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
            god, 'can-god', 'item', dict(
                name='A Rusted Tin Can',
                description='The label has been torn off. A patch of adhesive is still a little sticky, though the metal is all rusted over. Something about it is unsettling.'))
        bag = GameObject.create_scripted_object(
            god, 'bag-god', 'item', dict(
                name='A Garbage Bag',
                description="It's just a garbage bag. The black, glossy kind. You wonder how much stuff you could fit in there."))

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
        self.can.set_perm('carry', 'owner')

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
            self.god, 'can-shiny-god', 'item', dict(
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

@mock.patch('tmserver.world.GameWorld.user_hears')
class DropTest(InventoryTestCase):
    def test_success(self, mock_hears):
        GameWorld.handle_get(self.vil, 'can')
        assert self.can in self.vil.contains
        GameWorld.handle_drop(self.vil, 'can')
        assert self.can not in self.vil.contains
        assert self.can in self.foyer.contains
        assert mock_hears.called

    def test_ambiguity(self, mock_hears):
        shiny_can = GameObject.create_scripted_object(
            self.god, 'can-shiny-god', 'item', dict(
                name='A New, Shiny Tin Can',
                description="A new can. Not even adhesive on this. You can see yourself in its reflection but you're all ripply."))
        GameWorld.put_into(self.foyer, shiny_can)
        GameWorld.handle_get(self.vil, 'can')
        GameWorld.handle_get(self.vil, 'can')
        assert self.can in self.vil.contains
        assert shiny_can in self.vil.contains
        GameWorld.handle_drop(self.vil, 'can')
        assert self.can not in self.vil.contains
        assert shiny_can in self.vil.contains
        assert mock_hears.called

@mock.patch('tmserver.world.GameWorld.user_hears')
class PutTest(InventoryTestCase):
    def test_malformed(self, _):
        malformed = [
            'can zorp bag',
            'can',
            'can from bag',
            'caninbag',
            'can bag',
            'can i n bag']
        for bad in malformed:
            with self.assertRaisesRegex(
                    ClientException,
                    'Try /put some'):
                GameWorld.handle_put(self.vil, bad)

    def test_with_spaces(self, mock_hears):
        GameWorld.handle_put(self.vil, 'tin can in bag')
        assert self.can in self.bag.contains
        assert self.can not in self.foyer.contains
        assert self.can not in self.vil.contains
        assert mock_hears.called

    def test_target_not_found(self, _):
        with self.assertRaisesRegex(
                ClientException,
                'You look in vain for shoe.'):
            GameWorld.handle_put(self.vil, 'shoe in bag')

    def test_target_in_inv(self, mock_hears):
        GameWorld.handle_get(self.vil, 'can')
        GameWorld.handle_put(self.vil, 'can in bag')
        assert self.can in self.bag.contains
        assert self.can not in self.vil.contains
        assert mock_hears.called

    def test_target_in_room(self, mock_hears):
        GameWorld.handle_put(self.vil, 'can in bag')
        assert self.can in self.bag.contains
        assert self.can not in self.foyer.contains
        assert self.can not in self.vil.contains
        assert mock_hears.called

    def test_container_in_inv(self, mock_hears):
        GameWorld.handle_get(self.vil, 'bag')
        GameWorld.handle_put(self.vil, 'can in bag')
        assert self.can in self.bag.contains
        assert self.can not in self.vil.contains
        assert mock_hears.called

    def test_both_in_inv(self, mock_hears):
        GameWorld.handle_get(self.vil, 'bag')
        GameWorld.handle_get(self.vil, 'can')
        GameWorld.handle_put(self.vil, 'can in bag')
        assert self.can in self.bag.contains
        assert self.can not in self.vil.contains
        assert mock_hears.called

    def test_container_not_found(self, _):
        with self.assertRaisesRegex(
                ClientException,
                'You look in vain for pail.'):
            GameWorld.handle_put(self.vil, 'can in pail')

    def test_target_denied(self, _):
        self.can.set_perm('carry', 'owner')
        with self.assertRaisesRegex(
                ClientException, 'You grab a hold of A Rusted Tin Can but'):
            GameWorld.handle_put(self.vil, 'can in bag')

    def test_container_denied(self, _):
        self.bag.set_perm('execute', 'owner')
        with self.assertRaisesRegex(
                ClientException,
                'You try as hard as you can, but you are unable to pry open A Garbage Bag'):
            GameWorld.handle_put(self.vil, 'can in bag')


@mock.patch('tmserver.world.GameWorld.user_hears')
class RemoveTest(InventoryTestCase):
    def test_malformed(self, _):
        malformed = [
            'can zorp bag',
            'can',
            'can bag',
            'can f r o m bag',
            'can in bag',
            'canfrombag']
        for bad in malformed:
            with self.assertRaisesRegex(
                    ClientException,
                    'Try /remove some'):
                GameWorld.handle_remove(self.vil, bad)

    def test_target_not_found(self, _):
        with self.assertRaisesRegex(
                ClientException,
                'You look in vain for shoe.'):
            GameWorld.handle_remove(self.vil, 'shoe from bag')

    def test_container_in_inv(self, mock_hears):
        GameWorld.handle_get(self.vil, 'bag')
        GameWorld.handle_put(self.vil, 'can in bag')
        assert self.can not in self.vil.contains
        assert self.can in self.bag.contains
        GameWorld.handle_remove(self.vil, 'can from bag')
        assert self.can in self.vil.contains
        assert self.can not in self.bag.contains
        assert mock_hears.called

    def test_container_in_room(self, mock_hears):
        GameWorld.handle_put(self.vil, 'can in bag')
        assert self.can not in self.vil.contains
        assert self.can in self.bag.contains
        GameWorld.handle_remove(self.vil, 'can from bag')
        assert self.can in self.vil.contains
        assert self.can not in self.bag.contains
        assert mock_hears.called

    def test_container_not_found(self, _):
        with self.assertRaisesRegex(
                ClientException,
                'You look in vain for pail.'):
            GameWorld.handle_remove(self.vil, 'shoe from pail')

    def test_target_denied(self, _):
        GameWorld.handle_put(self.vil, 'can in bag')
        self.can.set_perm('carry', 'owner')
        with self.assertRaisesRegex(
                ClientException, 'You grab a hold of A Rusted Tin Can but'):
            GameWorld.handle_remove(self.vil, 'can from bag')

    def test_container_denied(self, _):
        self.bag.set_perm('execute', 'owner')
        with self.assertRaisesRegex(
                ClientException,
                'You try as hard as you can, but you are unable to pry open A Garbage Bag'):
            GameWorld.handle_put(self.vil, 'can in bag')
