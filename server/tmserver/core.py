import asyncio
import logging
import re
import websockets as ws

from .errors import ClientException
from .models import UserAccount

LOGIN_RE = re.compile(r'^LOGIN ([^:\n]+?):(.+)$')
REGISTER_RE = re.compile(r'^REGISTER ([^:\n]+?):(.+)$')
COMMAND_RE = re.compile(r'^COMMAND ([^ ]+) ?(.*)$')


class UserSession:
    """An instance of this class represents a user's session."""
    def __init__(self, game_world, websocket):
        self.websocket = websocket
        self.game_world = game_world
        # TODO rename user_account
        self.user = None

    @property
    def associated(self):
        return self.user is not None

    def associate(self, user):
        self.user = user

    async def client_send(self, message):
        self.websocket.send(message)

    def dispatch_action(self, action, rest):
        self.game_world.dispatch_action(self.user, action, rest)

    def __str__(self):
        s = 'UserSession<{}>'.format(None)
        if self.associated:
            s = 'UserSession<{}>'.format(self.user.username)

        return s


class ConnectionMap:
    def __init__(self):
        self.connections = {}

    def add(self, websocket, user_session):
        self.connections[websocket] = user_session

    def get_session(self, websocket):
        return self.connections.get(websocket)


class GameServer:
    def __init__(self, game_world, bind='localhost', port=10014, logger=None):
        self.game_world = game_world
        if logger is None:
            logger = logging.getLogger('tmserver')
        self.bind = bind
        self.port = port
        self.connections = ConnectionMap()
        self.logger = logger

    async def handle_connection(self, websocket, path):
        self.logger.info('Handling initial connection at path {}'.format(path))
        user_session = UserSession(game_world, websocket)
        self.logger.info('Registering user context {}'.format(user_session))
        self.connections.add(websocket, user_session)
        async for message in websocket:
            await self.handle_message(user_session, message)

    async def handle_message(self, user_session, message):
        self.logger.info("Handling message '{}' for {}".format(
            message, user_session))
        try:
            if message.startswith('LOGIN'):
                self.handle_login(user_session, message)
                await user_session.clent_send('LOGIN OK')
            elif message.startswith('REGISTER'):
                self.handle_registration(user_session, message)
                await user_session.client_send('REGISTER OK')
            elif message.startswith('COMMAND'):
                # these incoming messages are now linked to a user session ->
                # user account -> player object. we have a bridge to the
                # client, but the actual definition of game commands hasn't
                # been done.
                #
                # i'd like to set up the scaffolding for a command -- like /go
                # <direction> or /look -- to round trip to the model layer and
                # back to the client.
                #
                # i can process the commands either here in the game server
                # (like with login and register), in the user session (blech),
                # in the user model (v blech). none of these feels particularly
                # natural to me.
                #
                # i think first i should probably decide on the actual
                # hierarchy of commands as well as routing chats.
                #
                # i can detect here in server if i'm seeing a CHAT (ie command
                # sent to the client with no punctuational prefix) or COMMAND.
                # This feels wrong immediately, though, since a CHAT should
                # just be another COMMAND.
                #
                # the client can detect a chat and send "COMMAND CHAT $rest".
                # In the case of a punctuational message typed by the user at
                # the client, it would be "COMMAND $command $rest". I'm find
                # with this as a starting point.
                #
                # should these be acked back to the client? probably -- it's
                # good for presence wrt the server connection.
                self.handle_command(user_session, message)
                await user_session.client_send('COMMAND OK')
            else:
                #await user_session.client_send('you said {}'.format(message))
                raise ClientException('message not understood')
        except ClientException as e:
            await user_session.client_send('ERROR: '.format(e))

    def handle_command(self, user_session, message):
        if not user_session.associated:
            raise ClientException('not logged in')
        action, rest = self.parse_command(message)
        user_session.dispatch_action(action, rest)

    def parse_command(self, message):
        match = COMMAND_RE.fullmatch(message)
        if match is None:
            raise ClientException('malformed command message: {}'.format(message))
        return match.groups()

    def handle_login(self, user_session, message):
        if user_session.associated:
            raise ClientException('log out first')
        username, password = self.parse_login(message)
        users = UserAccount.select().where(UserAccount.username==username)
        if len(users) == 0:
            raise ClientException('no such user')
        user = users[0]
        if user.check_password(password):
            user_session.associate(user)
        else:
            raise ClientException('bad password')

    def parse_login(self, message):
        match = LOGIN_RE.fullmatch(message)
        if match is None:
            raise ClientException('malformed login message: {}'.format(message))
        return match.groups()

    def handle_registration(self, user_session, message):
        if user_session.associated:
            raise ClientException('log out first')
        username, password = self.parse_registration(message)
        u = UserAccount(username=username, password=password)
        u.validate()
        u.save()

    def parse_registration(self, message):
        """Given a registration message like REGISTER vilmibm:abc123, parse and
        return the username and password."""
        match = REGISTER_RE.fullmatch(message)
        if match is None:
            raise ClientException('malformed registration message: {}'.format(message))
        return match.groups()

    def start(self):
        self.logger.info('Starting up asyncio loop')
        # I'm cargo culting these asyncio calls from the websockets
        # documentation
        asyncio.get_event_loop().run_until_complete(
            ws.serve(self.handle_connection, self.bind, self.port))
        asyncio.get_event_loop().run_forever()
