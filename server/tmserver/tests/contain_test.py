from ..migrations import bust_ghosts
from ..models import UserAccount, GameObject, Contains
from ..world import GameWorld

from .tm_test_case import TildemushTestCase


class ContainTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')
        self.room = GameObject.create_scripted_object(
            author=self.vil,
            shortname='foul-foyer',
            obj_type='room')
        self.phone = GameObject.create_scripted_object(
            author=self.vil,
            shortname='pixel-2')
        self.app = GameObject.create_scripted_object(
            author=self.vil,
            shortname='signal')

    def test_ghost_busting(self):
        player_obj = self.vil.player_obj
        GameWorld.put_into(self.room, player_obj)
        GameWorld.put_into(player_obj, self.phone)
        GameWorld.put_into(self.phone, self.app)
        assert player_obj in self.room.contains
        assert self.phone in player_obj.contains
        assert self.app in self.phone.contains
        import ipdb; ipdb.set_trace()
        bust_ghosts()
        assert player_obj not in self.room.contains
        assert self.phone in player_obj.contains
        assert self.app in self.phone.contains

    def test_player_obj(self):
        player_obj = self.vil.player_obj
        assert player_obj.name == self.vil.username
        assert player_obj.shortname == self.vil.username
        assert player_obj.user_account == self.vil
        assert player_obj.author == self.vil

    def test_area_of_effect(self):
        player_obj = self.vil.player_obj
        cigar = GameObject.create_scripted_object(
            author=self.vil,
            shortname='black-and-mild')
        rug = GameObject.create_scripted_object(
            author=self.vil,
            shortname='rug')
        ship = GameObject.create_scripted_object(
            author=self.vil,
            shortname='voyager',
            obj_type='room')

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

        assert GameWorld.area_of_effect(self.vil.player_obj) == {
            self.room,
            self.phone,
            cigar,
            rug,
            player_obj}

    def test_creating_contains(self):
        player_obj = self.vil.player_obj
        GameWorld.put_into(self.room, player_obj)
        GameWorld.put_into(player_obj, self.phone)
        GameWorld.put_into(self.phone, self.app)
        assert self.room == player_obj.room
        assert None == self.room.room
        assert self.phone == self.app.room
        assert [self.app] == list(self.phone.contains)
        assert [player_obj] == list(self.room.contains)
        assert [] == list(self.app.contains)

    def test_removing_contains(self):
        # This is a weird test since remove_from produces orphaned objects and
        # is only really used when players disconnect.
        player_obj = self.vil.player_obj
        GameWorld.put_into(self.room, player_obj)
        GameWorld.put_into(player_obj, self.phone)
        GameWorld.put_into(self.phone, self.app)
        assert self.phone == self.app.room
        assert [self.app] == list(self.phone.contains)
        GameWorld.remove_from(self.phone, self.app)
        assert [] == list(self.phone.contains)
        assert None == self.app.room

    def test_all_active_objects(self):
        player_obj = self.vil.player_obj
        cigar = GameObject.create_scripted_object(
            author=self.vil,
            shortname='black-and-mild')
        rug = GameObject.create_scripted_object(
            author=self.vil,
            shortname='rug')
        ship = GameObject.create_scripted_object(
            author=self.vil,
            shortname='voyager',
            obj_type='room')

        GameWorld.put_into(self.room, player_obj)
        GameWorld.put_into(self.phone, self.app)
        GameWorld.put_into(self.room, cigar)
        GameWorld.put_into(player_obj, self.phone)
        GameWorld.put_into(self.room, rug)
        GameWorld.put_into(ship, self.room)

        aoe = set(GameWorld.all_active_objects())

        assert aoe == {
            player_obj,
            cigar,
            rug,
            ship,
            self.room,
            self.phone,
            self.app,
        }
