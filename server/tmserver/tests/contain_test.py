from ..models import UserAccount, GameObject, Contains, GameWorld

from .tm_test_case import TildemushTestCase

class ContainTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount(
            username='vilmibm',
            password='foobarbazquux',
            display_name='a gaseous cloud')
        self.vil.hash_password()
        self.vil.save()

    def test_player_obj(self):
        assert self.vil.player_obj is None
        player_obj = self.vil.init_player_obj()
        assert self.vil.player_obj.name == self.vil.display_name
        assert player_obj.user_account == self.vil
        assert player_obj.author == self.vil

    def test_area_of_effect(self):
        self.vil.init_player_obj()
        room = GameObject.create(
            author=self.vil,
            name='foul foyer')
        cigar = GameObject.create(
            author=self.vil,
            name='black and mild',
            description='with the wood tip, naturally')
        phone = GameObject.create(
            author=self.vil,
            name='pixel 2')
        app = GameObject.create(
            author=self.vil,
            name='signal')
        rug = GameObject.create(
            author=self.vil,
            name='rug',
            description='a beautiful persian rug')
        ship = GameObject.create(
            author=self.vil,
            name='Voyager')

        Contains.create(
            outer_obj=room,
            inner_obj=self.vil.player_obj)
        Contains.create(
            outer_obj=phone,
            inner_obj=app)
        Contains.create(
            outer_obj=room,
            inner_obj=cigar)
        Contains.create(
            outer_obj=self.vil.player_obj,
            inner_obj=phone)
        Contains.create(
            outer_obj=room,
            inner_obj=rug)
        Contains.create(
            outer_obj=ship,
            inner_obj=room)
        # TODO so this equality check will likely fail, we'll see
        # TODO probably add a custom hash method for objects
        assert GameWorld.area_of_effect(self.vil) == {
            room,
            phone,
            cigar,
            rug}

    def test_creating_contains(self):
        pass

    def test_removing_contains(self):
        pass
