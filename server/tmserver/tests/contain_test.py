from ..models import UserAccount, GameObject, Contains

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
        pass

    def test_creating_contains(self):
        pass

    def test_removing_contains(self):
        pass
