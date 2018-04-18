from ..models import UserAccount, GameObject, Contains

from .tm_test_case import TildemushTestCase

class RoomTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccout(
            username='vilmibm',
            password='foobarbazquux')
        self.vil.hash_password()
        self.vil.save()
