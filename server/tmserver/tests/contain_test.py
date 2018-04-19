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
        self.room = GameObject.create(
            author=self.vil,
            name='foul foyer')
        self.phone = GameObject.create(
            author=self.vil,
            name='pixel 2')
        self.app = GameObject.create(
            author=self.vil,
            name='signal')

    def test_player_obj(self):
        assert self.vil.player_obj is None
        player_obj = self.vil.init_player_obj()
        assert self.vil.player_obj.name == self.vil.display_name
        assert player_obj.user_account == self.vil
        assert player_obj.author == self.vil

    def test_area_of_effect(self):
        player_obj = self.vil.init_player_obj()
        cigar = GameObject.create(
            author=self.vil,
            name='black and mild',
            description='with the wood tip, naturally')
        rug = GameObject.create(
            author=self.vil,
            name='rug',
            description='a beautiful persian rug')
        ship = GameObject.create(
            author=self.vil,
            name='Voyager')

        Contains.create(
            outer_obj=self.room,
            inner_obj=player_obj)
        Contains.create(
            outer_obj=self.phone,
            inner_obj=self.app)
        Contains.create(
            outer_obj=self.room,
            inner_obj=cigar)
        Contains.create(
            outer_obj=player_obj,
            inner_obj=self.phone)
        Contains.create(
            outer_obj=self.room,
            inner_obj=rug)
        Contains.create(
            outer_obj=ship,
            inner_obj=self.room)

        assert GameWorld.area_of_effect(self.vil) == {
            self.room,
            self.phone,
            cigar,
            rug,
            player_obj}

    def test_creating_contains(self):
        player_obj = self.vil.init_player_obj()
        GameWorld.put_into(self.room, player_obj)
        GameWorld.put_into(player_obj, self.phone)
        GameWorld.put_into(self.phone, self.app)
        assert self.room == player_obj.contained_by
        assert self.phone == self.app.contained_by
        assert None == self.room.contained_by
        assert [self.app] == list(self.phone.contains)
        assert [player_obj] == list(self.room.contains)
        assert [] == list(self.app.contains)


    def test_removing_contains(self):
        pass
