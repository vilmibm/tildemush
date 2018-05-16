import unittest.mock as mock

from ..errors import ClientException
from ..models import UserAccount
from ..core import GameServer, UserSession
from ..world import GameWorld

from .tm_test_case import TildemushTestCase

class CommandTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.log_mock = mock.Mock()
        self.server = GameServer(GameWorld, logger=self.log_mock)
        self.user_session = UserSession(None, GameWorld, None)
        self.vil = UserAccount.create(username='vilmibm', password='foobarbazquux')
        msg = 'LOGIN vilmibm:foobarbazquux'
        self.server.handle_login(self.user_session, msg)

    def test_parses_command(self):
        command_msgs = [
            ('COMMAND go somewhere',
             ('go', 'somewhere')),
            ('COMMAND look',
             ('look', '')),
            ('COMMAND fly-away',
             ('fly-away', '')),
            ('COMMAND neatly-eat a banana',
             ('neatly-eat', 'a banana')),
            ('COMMAND write a really long and involved novel',
             ('write', 'a really long and involved novel')),
            ('COMMAND say hello, all; how are you?',
             ('say', 'hello, all; how are you?')),
            ("COMMAND whisper and then i says, 'hey i'm eatin here'",
             ('whisper', "and then i says, 'hey i'm eatin here'")),
            ('COMMAND hideous!pathological;command.why some arguments',
             ('hideous!pathological;command.why', 'some arguments'))]

        with mock.patch('tmserver.world.GameWorld.dispatch_action') as world_dispatch_mock:
            for msg, expected in command_msgs:
                self.server.handle_command(self.user_session, msg)
                world_dispatch_mock.assert_called_with(*([self.vil.player_obj] + list(expected)))

    def test_detects_malformed_command(self):
        malformed_msgs = [
            'COMMAND  go somewhere',
            'COMMAND  go   somewhere', # this might seem harsh but the client should be collapsing spaces
            'COMMANDgo',
            'COMMAND',
            'COMMAND ',
            'COMMAND  ']
        for malformed in malformed_msgs:
            with self.assertRaisesRegex(
                    ClientException,
                    'malformed command message: {}'.format(malformed)):
                self.server.handle_command(self.user_session, malformed)

    def test_rejects_unauthenticated_command(self):
        user_session = UserSession(None, GameWorld, None)
        with self.assertRaisesRegex(
                ClientException,
                'not logged in'):
            self.server.handle_command(user_session, 'COMMAND go')
