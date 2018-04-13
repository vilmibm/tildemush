import unittest.mock as mock
import unittest

from ..errors import ClientException
from ..migrations import reset_db
from ..models import User
from ..core import GameServer, UserSession
from .tm_test_case import TildemushTestCase

class TestRegistration(TildemushTestCase):

    def setUp(self):
        super().setUp()
        self.log_mock = mock.Mock()
        self.server = GameServer(logger=self.log_mock)
        self.mock_session = mock.Mock()
        self.mock_session.associated = False

    def test_malformed_registers(self):
        malformed_registrations = [
            'REGISTERpuke',
            'REGISTER foobar',
            'REGISTER foo\n:bar',
            'REGISTER foo:',
            'REGISTER :bar',
            'REGISTER ::::bar',
            'REGISTER foo:ba\nr',
        ]
        for malformed in malformed_registrations:
            expected_msg = 'malformed registration message: {}'
            with self.assertRaisesRegex(
                    ClientException,
                    expected_msg.format(malformed)):
                self.server.parse_registration(malformed)

    def test_creates_user(self):
        msg = 'REGISTER vilmibm:foobar1234567890-=_+!@#$%^&*()_+{}[]|/.,<>;:\'"'
        self.server.handle_registration(self.mock_session, msg)
        users = User.select().where(User.username == 'vilmibm')
        self.assertEqual(1, len(users))

    def test_validates_user(self):
        with mock.patch('tmserver.models.User.validate') as m:
            msg = 'REGISTER vilmibm:foobar'
            self.server.handle_registration(self.mock_session, msg)
        m.assert_called()

    def test_hashes_user_password(self):
        with mock.patch('tmserver.models.User.hash_password') as m:
            msg = 'REGISTER vilmibm:foobarbazquux'
            self.server.handle_registration(self.mock_session, msg)
        m.assert_called()

    def test_detects_already_assoced_user_session(self):
        vil = User(username='vilmibm', password='foobarbazquux')
        vil.hash_password()
        vil.save()
        user_session = UserSession(mock.Mock())
        user_session.associate(vil)
        with self.assertRaisesRegex(
                ClientException,
                'log out first'):
            self.server.handle_registration(user_session, 'LOGIN vilmibm:foobarbazquux')
