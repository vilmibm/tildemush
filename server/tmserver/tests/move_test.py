import unittest.mock as mock
from ..core import GameServer, UserSession
from ..models import UserAccount, GameObject, Contains
from ..world import GameWorld

from .tm_test_case import TildemushTestCase

class MoveTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.same = UserAccount.create(
            username='selfsame',
            password='foobarbazquux')
        user_session = UserSession(None, GameWorld, mock.Mock())
        user_session.associate(self.same)
        self.pond = GameObject.create_scripted_object(
            author=self.same,
            shortname='pond',)
        self.cabin = GameObject.create_scripted_object(
            author=self.same,
            shortname='cabin',)
        self.frog = GameObject.create_scripted_object(
            author=self.same,
            shortname='dumb frog')
        self.roof = GameObject.create_scripted_object(
            author=self.same,
            shortname='roof',)

    def test_moving(self):
        player_obj = self.same.player_obj
        GameWorld.put_into(self.pond, player_obj)
        GameWorld.put_into(self.pond, self.frog)

        # can't go to non existing exit
        GameWorld.handle_move(player_obj, 'north')
        assert self.pond == player_obj.contained_by

        # can move to object
        GameWorld.handle_move(player_obj, 'cabin')
        assert self.cabin == player_obj.contained_by

        # can't move into self
        GameWorld.handle_move(player_obj, 'selfsame')
        assert self.cabin == player_obj.contained_by

        # can move to existing exit
        GameWorld.create_exit(player_obj, 'ladder', 'above roof a ladder')
        GameWorld.handle_go(player_obj, 'above')
        assert self.roof == player_obj.contained_by

        # can move using aliases
        GameWorld.handle_go(player_obj, 'down')
        assert self.cabin == player_obj.contained_by

        GameWorld.handle_go(player_obj, 'u')
        assert self.roof == player_obj.contained_by

        GameWorld.handle_go(player_obj, 'd')
        assert self.cabin == player_obj.contained_by

        GameWorld.handle_go(player_obj, 'up')
        assert self.roof == player_obj.contained_by

