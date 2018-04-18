import asyncio
import logging
import re
import websockets as ws

from .errors import ClientException
from .models import UserAccount

LOGIN_RE = re.compile(r'^LOGIN ([^:\n]+?):(.+)$')
REGISTER_RE = re.compile(r'^REGISTER ([^:\n]+?):(.+)$')


class UserSession:
    """An instance of this class represents a user's session."""
    def __init__(self, websocket):
        self.websocket = websocket
        self.user = None

    def associate(self, user):
        self.user = user

    @property
    def associated(self):
        return self.user is not None

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
    def __init__(self, bind='localhost', port=10014, logger=None):
        if logger is None:
            logger = logging.getLogger('tmserver')
        self.bind = bind
        self.port = port
        self.connections = ConnectionMap()
        self.logger = logger

    async def handle_connection(self, websocket, path):
        self.logger.info('Handling initial connection at path {}'.format(path))
        user_session = UserSession(websocket)
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
                await user_session.websocket.send('LOGIN OK')
            elif message.startswith('REGISTER'):
                self.handle_registration(user_session, message)
                await user_session.websocket.send('REGISTER OK')
            else:
                # TODO for now, just echo
                await user_session.websocket.send('you said {}'.format(message))
        except ClientException as e:
            await user_session.websocket.send('ERROR: '.format(e))

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
        u.hash_password()
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
