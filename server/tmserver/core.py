import asyncio
import logging
import json
import re

import websockets as ws

from .errors import ClientException, UserValidationError
from .models import UserAccount, GameObject

LOGIN_RE = re.compile(r'^LOGIN ([^:\n]+?):(.+)$')
REGISTER_RE = re.compile(r'^REGISTER ([^:\n]+?):(.+)$')
COMMAND_RE = re.compile(r'^COMMAND ([^ ]+) ?(.*)$')

LOOP = asyncio.get_event_loop()


class UserSession:
    """An instance of this class represents a user's session."""
    def __init__(self, loop, game_world, websocket):
        self.loop = loop
        self.websocket = websocket
        self.game_world = game_world
        self.user_account = None

    @property
    def associated(self):
        return self.user_account is not None

    def associate(self, user_account):
        self.user_account = user_account
        self.game_world.register_session(user_account, self)
        foyer = GameObject.select().where(GameObject.shortname=='foyer')[0]
        self.game_world.put_into(foyer, user_account.player_obj)
        # TODO thread through disconnect handling to dematerialize player objects

    def handle_hears(self, sender_obj, message):
        # TODO delete sender_obj argument i think?
        # we will need to support basic abuse control like blocking other
        # users, so having a sender_obj here might be useful for interaction
        # filtering. rn it's unused though.
        asyncio.ensure_future(
            self.client_send(message),
            loop=self.loop)

    def handle_client_update(self, client_state):
        asyncio.ensure_future(
            self.client_send('STATE {}'.format(json.dumps(client_state))),
            loop=self.loop)

    async def client_send(self, message):
        await self.websocket.send(message)

    def dispatch_action(self, action, action_args):
        self.game_world.dispatch_action(
            self.user_account.player_obj,
            action,
            action_args)

    def __str__(self):
        s = 'UserSession<{}>'.format(None)
        if self.associated:
            s = 'UserSession<{}>'.format(self.user_account.username)

        return s


class ConnectionMap:
    def __init__(self):
        self.connections = {}

    def add(self, websocket, user_session):
        self.connections[websocket] = user_session

    def get_session(self, websocket):
        return self.connections.get(websocket)


class GameServer:
    def __init__(self, game_world, loop=LOOP, bind='127.0.0.1', port=10014, logger=None):
        self.loop = loop
        self.game_world = game_world
        if logger is None:
            logger = logging.getLogger('tmserver')
        self.bind = bind
        self.port = port
        self.connections = ConnectionMap()
        self.logger = logger

    async def handle_connection(self, websocket, path):
        self.logger.info('Handling initial connection at path {}'.format(path))
        user_session = UserSession(self.loop, self.game_world, websocket)
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
                self.logger.info('telling {} about having logged them in'.format(
                    user_session.user_account.username))
                await user_session.client_send('LOGIN OK')
            elif message.startswith('REGISTER'):
                try:
                    self.handle_registration(user_session, message)
                    await user_session.client_send('REGISTER OK')
                except UserValidationError as e:
                    await user_session.client_send('ERROR: {}'.format(e))
            elif message.startswith('COMMAND'):
                self.handle_command(user_session, message)
                await user_session.client_send('COMMAND OK')
            elif message.startswith('PING'):
                await user_session.client_send('PONG')
            else:
                # TODO clients should format said things (ie things a user
                # types not prefixed with a / command) with "COMMAND SAY"
                #await user_session.client_send('you said {}'.format(message))
                raise ClientException('message not understood')
        except ClientException as e:
            await user_session.client_send('ERROR: {}'.format(e))

    def handle_command(self, user_session, message):
        if not user_session.associated:
            raise ClientException('not logged in')
        action, action_args = self.parse_command(message)
        user_session.dispatch_action(action, action_args)

    def parse_command(self, message):
        match = COMMAND_RE.fullmatch(message)
        if match is None:
            raise ClientException('malformed command message: {}'.format(message))
        return match.groups()

    def handle_login(self, user_session, message):
        if user_session.associated:
            raise ClientException('log out first')
        username, password = self.parse_login(message)
        user_accounts = UserAccount.select().where(UserAccount.username==username)
        if len(user_accounts) == 0:
            raise ClientException('no such user')
        user_account = user_accounts[0]
        if user_account.check_password(password):
            self.logger.info('logging in user {}'.format(user_account.username))
            user_session.associate(user_account)
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
        self.loop.run_until_complete(
            ws.serve(self.handle_connection, self.bind, self.port, loop=self.loop))
        self.loop.run_forever()

    def _get_ws_server(self):
        return ws.serve(self.handle_connection, self.bind, self.port, loop=self.loop)
