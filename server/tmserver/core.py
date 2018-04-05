import asyncio
import re
import websockets as ws

from .logs import debug_logger
from .models import User

REGISTER_RE = re.compile(r'^REGISTER ([^:\n]+?):(.+)$')


class UserContext:
    """An instance of this class represents a user's session."""
    def __init__(self, websocket):
        self.websocket = websocket


class GameServer:
    def __init__(self, bind='localhost', port=10014, logger=debug_logger):
        self.bind = bind
        self.port = port
        self.connections = set()
        self.logger = logger

    async def handle_connection(self, websocket, path):
        self.logger.info('Handling initial connection at path {}'.format(path))
        user_ctx = UserContext(websocket)
        self.logger.info('Registering user context {}'.format(user_ctx))
        self.connections.add(user_ctx)
        async for message in websocket:
            await self.handle_message(user_ctx, message)

    async def handle_message(self, user_ctx, message):
        self.logger.info("Handling message '{}' for {}".format(
            message, user_ctx))
        if message.startswith('AUTH'):
            # TODO actually validate un/pw
            # TODO connect context to user account
            await user_ctx.websocket.send('AUTH OK')
        elif message.startswith('REGISTER'):
            self.handle_registration(message)
            await user_ctx.websocket.send('REGISTER OK')
        else:
            # TODO for now, just echo
            await user_ctx.websocket.send('you said {}'.format(message))

    @classmethod
    def handle_registration(cls, message):
        username, password = cls.parse_registration(message)
        u = User(username=username, password=password)
        u.validate()
        u.hash_password()
        u.save()

    @classmethod
    def parse_registration(cls, message):
        """Given a registration message like REGISTER vilmibm:abc123, parse and
        return the username and password."""
        match = REGISTER_RE.fullmatch(message)
        if match is None:
            raise Exception('malformed registration message: {}'.format(message))
        return match.groups()

    def start(self):
        self.logger.info('Starting up asyncio loop')
        # I'm cargo culting these asyncio calls from the websockets
        # documentation
        asyncio.get_event_loop().run_until_complete(
            ws.serve(self.handle_connection, self.bind, self.port))
        asyncio.get_event_loop().run_forever()
