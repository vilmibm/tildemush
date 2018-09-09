from unittest import mock

from ..errors import UserError
from ..world import GameWorld

from .tm_test_case import TildemushUnitTestCase

class TestModeCommand(TildemushUnitTestCase):
    def test_malformed(self):
        malformed = [
            'no good',
            'bad',
            '',
            'really not a good idea']
        for m in malformed:
            with self.assertRaisesRegex(UserError, 'try /mode'):
                GameWorld.handle_mode(None, m)

    def test_not_found(self):
        with self.assertRaisesRegex(UserError, 'You look in vain for'):
            with mock.patch('tmserver.GameWorld.resolve_obj', return_value=None):
                GameWorld.handle_mode(None, 'foo bar baz')

    def test_bad_perm(self):
        with self.assertRaisesRegex(UserError, 'invalid permission'):
            with mock.patch('tmserver.GameWorld.resolve_obj', return_value='fake'):
                GameWorld.handle_mode(None, 'foo bar baz')

    def test_bad_value(self):
        with self.assertRaisesRegex(UserError, 'invalid value'):
            with mock.patch('tmserver.GameWorld.resolve_obj', return_value='fake'):
                GameWorld.handle_mode(None, 'foo carry baz')
