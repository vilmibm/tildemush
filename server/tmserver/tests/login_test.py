import unittest.mock as mock
import unittest

from ..errors import ClientException
from ..models import UserAccount
from ..core import GameServer, UserSession
from ..world import GameWorld

from .tm_test_case import TildemushTestCase

class TestLogin(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.log_mock = mock.Mock()
        self.server = GameServer(GameWorld, logger=self.log_mock)

    def test_malformed_login(self):
        malformed_logins = [
            'LOGINpuke',
            'LOGIN :foo',
            'LOGIN foo:',
            'LOGIN f\noo:bar',
            'LOGIN foo bar',
            'LOGIN foobar',
            'LOGIN :foo:bar',
        ]
        for malformed in malformed_logins:
            expected_msg = 'malformed login message'
            with self.assertRaisesRegex(
                    ClientException,
                    expected_msg.format(malformed)):
                self.server.parse_login(malformed)

    def test_user_not_found(self):
        vil = UserAccount.create(username='vilmibm', password='12345678901')
        msg = 'LOGIN vilmibbm:foobarbazquux'
        with self.assertRaisesRegex(
                ClientException,
                'no such user'):
            self.server.handle_login(UserSession(GameWorld, None), msg)

    def test_bad_password(self):
        vil = UserAccount.create(username='vilmibm', password='12345678901')
        msg = 'LOGIN vilmibm:foobarbazquux'
        with self.assertRaisesRegex(
                ClientException,
                'bad password'):
            self.server.handle_login(UserSession(GameWorld, None), msg)

    def test_success(self):
        user_session = UserSession(GameWorld, None)
        vil = UserAccount.create(username='vilmibm', password='foobarbazquux')
        msg = 'LOGIN vilmibm:foobarbazquux'
        self.server.handle_login(user_session, msg)
        self.assertTrue(user_session.associated)
        self.assertEqual(user_session.user_account.username, 'vilmibm')
        self.assertEqual('UserSession<vilmibm>', str(user_session))
        assert GameWorld.get_session(vil.id) is user_session

    def test_detects_already_assoced_user_session(self):
        vil = UserAccount.create(username='vilmibm', password='foobarbazquux')
        user_session = UserSession(GameWorld, mock.Mock())
        user_session.associate(vil)
        with self.assertRaisesRegex(
                ClientException,
                'log out first'):
            self.server.handle_login(user_session, 'LOGIN vilmibm:foobarbazquux')
