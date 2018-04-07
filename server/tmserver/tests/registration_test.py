import unittest.mock as mock
import unittest

from ..migrations import reset_db
from ..models import User
from ..core import GameServer

class TestRegistration(unittest.TestCase):

    def setUp(self):
        reset_db()

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
            expected_msg = 'malformed registration message : {}'
            with self.assertRaises(
                    Exception, msg=expected_msg.format(malformed)):
                GameServer.parse_registration(malformed)

    def test_creates_user(self):
        msg = 'REGISTER vilmibm:foobar1234567890-=_+!@#$%^&*()_+{}[]|/.,<>;:\'"'
        GameServer.handle_registration(msg)
        users = User.select().where(User.username == 'vilmibm')
        self.assertEqual(1, len(users))

    def test_validates_user(self):
        with mock.patch('tmserver.models.User.validate') as m:
            msg = 'REGISTER vilmibm:foobar'
            GameServer.handle_registration(msg)
        m.assert_called()

    def test_hashes_user_password(self):
        with mock.patch('tmserver.models.User.hash_password') as m:
            msg = 'REGISTER vilmibm:foobarbazquux'
            GameServer.handle_registration(msg)
        m.assert_called()

