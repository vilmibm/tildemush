import unittest

from ..models import UserAccount
from .tm_test_case import TildemushTestCase

class TestUserAccountModel(TildemushTestCase):
    def test_password_hashing(self):
        u = UserAccount(username='vilmibm', password='foobarbazquux')
        self.assertIsNotNone(u.password)
        u.save()
        u = UserAccount.select().where(UserAccount.username=='vilmibm')[0]
        self.assertTrue(u.check_password('foobarbazquux'))

    def test_can_create(self):
        u = UserAccount.create(username='vilmibm', password='foobar')
        self.assertTrue(u.check_password('foobar'))

    # validation stuff

    def test_username_taken(self):
        UserAccount.create(username='vilmibm', password='foo')
        u = UserAccount(username='vilmibm', password='bar')
        with self.assertRaisesRegex(
                Exception,
                'username taken: vilmibm'):
            u.validate()


    def test_username_invalid(self):
        bad_usernames = [
            'foo:',
            'foo\'',
            'foo"',
            'foo;',
            'fo%',
        ]
        for bad in bad_usernames:
            u = UserAccount(username=bad, password='foobarbazquux')
            with self.assertRaisesRegex(
                    Exception,
                    'username has invalid character'):
                u.validate()


    def test_password_insecure(self):
        u = UserAccount(username='hello', password='foobar')
        with self.assertRaisesRegex(
                Exception,
                'password too short'):
            u.validate()
