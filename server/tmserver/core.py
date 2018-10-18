import asyncio
import logging
import json
import re

import websockets as ws

from .errors import ClientError, UserValidationError, RevisionError, ClientQuit, UserError
from .models import UserAccount

LOGIN_RE = re.compile(r'^LOGIN ([^:\n]+?):(.+)$')
REGISTER_RE = re.compile(r'^REGISTER ([^:\n]+?):(.+)$')
COMMAND_RE = re.compile(r'^COMMAND ([^ ]+) ?(.*)$')
REVISION_RE = re.compile(r'^REVISION (.+)$')
# TODO ensure that object shortnames are ending up in the client state so they
# can be sent in REVISION messages
REVISION_KEYS = ('shortname', 'code', 'current_rev')

LOOP = asyncio.get_event_loop()


# TODO auth_required login for checking associated user_sessions

class UserSession:
    """An instance of this class represents a user's session."""
    def __init__(self, loop, game_world, websocket, logger=None):
        if logger is None:
            logger = logging.getLogger('tmserver')
        self.logger = logger
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

    def send_object_state(self, object_state):
        asyncio.ensure_future(
            self.client_send('OBJECT {}'.format(json.dumps(object_state))),
            loop=self.loop)

    async def client_send(self, message):
        self.logger.info("-> '{}' to {}".format(message, self))
        await self.websocket.send(message)

    def dispatch_action(self, action, action_args):
        self.game_world.dispatch_action(
            self.user_account.player_obj,
            action,
            action_args)

    def handle_revision(self, shortname, code, current_rev):
        return_payload = None
        revision_exception = None
        try:
            return_payload = self.game_world.handle_revision(
                self.user_account.player_obj,
                shortname,
                code,
                current_rev)
        except RevisionError as e:
            return_payload = e.payload
            revision_exception = str(e)

        return return_payload, revision_exception

    def handle_map(self):
        return self.game_world.render_map(self.user_account.player_obj)

    def handle_disconnect(self):
        if not self.associated:
            return
        player_obj = self.user_account.player_obj
        self.game_world.unregister_session(self.user_account)

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

    def remove(self, websocket):
        if websocket in self.connections:
            del self.connections[websocket]

    def get_session(self, websocket):
        return self.connections.get(websocket)


class GameServer:
    def __init__(self, game_world, loop=LOOP, bind='127.0.0.1', port=10014, logger=None):
        self.loop = loop
        self.game_world = game_world
        if logger is None:
            logger = logging.getLogger('tmserver')
        self.logger = logger
        self.bind = bind
        self.port = port
        self.connections = ConnectionMap()

    async def handle_connection(self, websocket, path):
        self.logger.info('Handling initial connection at path {}'.format(path))
        user_session = UserSession(self.loop, self.game_world, websocket)
        self.logger.info('Registering user context {}'.format(user_session))
        self.connections.add(websocket, user_session)
        try:
            async for message in websocket:
                await self.handle_message(user_session, message)
        except (ws.exceptions.ConnectionClosed, ClientQuit):
            self.logger.info('Client disconnect {}'.format(user_session))
            user_session.handle_disconnect()
            self.connections.remove(websocket)

    async def handle_message(self, user_session, message):
        self.logger.info("<- '{}' from {}".format(
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
                try:
                    self.handle_command(user_session, message)
                except UserError as e:
                    await user_session.client_send('{{red}}{}{{/}}'.format(e))
                else:
                    # TODO consider switching this to COMMAND ACK and sending
                    # as soon as we get the command. This is really only useful
                    # in that it tells the client "yes, i saw you; if you don't
                    # get a response it's not because i didn't see you."
                    await user_session.client_send('COMMAND OK')
            elif message.startswith('REVISION'):
                revision_result, revision_exception = self.handle_revision(user_session, message)
                if revision_exception:
                    # TODO consider something more specific than ERROR
                    await user_session.client_send('ERROR: {}'.format(revision_exception))
                user_session.send_object_state(revision_result)
            elif message.startswith('MAP'):
                # For now, we return a map of the room a user is currently in +
                # what they can reach in 2 hops. In the future this message
                # could include a room to arbitrarily map from (ie as a user
                # scrolls the map client side).
                rendered_map = self.handle_map(user_session)
                await user_session.client_send('MAP\n{}'.format(rendered_map))
            elif message.startswith('QUIT'):
                self.logger.info('Client quit {}'.format(user_session))
                raise ClientQuit()
            elif message.startswith('PING'):
                await user_session.client_send('PONG')
            else:
                # TODO clients should format said things (ie things a user
                # types not prefixed with a / command) with "COMMAND SAY"
                #await user_session.client_send('you said {}'.format(message))
                raise ClientError('message not understood')
        except ClientError as e:
            await user_session.client_send('ERROR: {}'.format(e))

    def handle_command(self, user_session, message):
        if not user_session.associated:
            raise ClientError('not logged in')
        action, action_args = self.parse_command(message)
        user_session.dispatch_action(action, action_args)

    def parse_command(self, message):
        match = COMMAND_RE.fullmatch(message)
        if match is None:
            raise ClientError('malformed command message: {}'.format(message))
        return match.groups()

    def handle_login(self, user_session, message):
        if user_session.associated:
            raise ClientError('log out first')
        username, password = self.parse_login(message)
        user_accounts = UserAccount.select().where(UserAccount.username==username)
        if len(user_accounts) == 0:
            raise ClientError('no such user')
        user_account = user_accounts[0]
        if user_account.check_password(password):
            self.logger.info('logging in user {}'.format(user_account.username))
            user_session.associate(user_account)
        else:
            raise ClientError('bad password')

    def parse_login(self, message):
        match = LOGIN_RE.fullmatch(message)
        if match is None:
            raise ClientError('malformed login message: {}'.format(message))
        return match.groups()

    def handle_registration(self, user_session, message):
        if user_session.associated:
            raise ClientError('log out first')
        username, password = self.parse_registration(message)
        u = UserAccount(username=username, password=password)
        u.validate()
        u.save()

    def parse_registration(self, message):
        """Given a registration message like REGISTER vilmibm:abc123, parse and
        return the username and password."""
        match = REGISTER_RE.fullmatch(message)
        if match is None:
            raise ClientError('malformed registration message: {}'.format(message))
        return match.groups()

    def handle_revision(self, user_session, message):
        if not user_session.associated:
            raise ClientError('not logged in')
        payload = self.parse_revision(message)
        return user_session.handle_revision(**payload)

    def parse_revision(self, message):
        match = REVISION_RE.fullmatch(message)
        if match is None:
            raise ClientError('malformed revision payload: {}'.format(message))
        payload = match.groups()[0]

        try:
            payload = json.loads(payload)
        except Exception as e:
            raise ClientError('failed to parse revision payload: {}'.format(payload))

        # TODO ensure it's a dict, raise otherwise

        for k in REVISION_KEYS:
            if payload.get(k) is None:
                raise ClientError('revision payload missing key: {}'.format(k))

        return payload

    def handle_map(self, user_session):
        if not user_session.associated:
            raise ClientError('not logged in')
        return user_session.handle_map()


    def start(self):
        self.logger.info('Starting up asyncio loop')
        # I'm cargo culting these asyncio calls from the websockets
        # documentation
        self.loop.run_until_complete(
            ws.serve(self.handle_connection, self.bind, self.port, loop=self.loop))
        self.loop.run_forever()

    def _get_ws_server(self):
        return ws.serve(self.handle_connection, self.bind, self.port, loop=self.loop)
