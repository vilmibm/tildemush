import asyncio
import websockets as ws

from .logs import logger


class UserContext:
    """An instance of this class represents a user's session."""
    def __init__(self, websocket):
        self.websocket = websocket


class GameServer:
    def __init__(self, bind='localhost', port=10014):
        self.bind = bind
        self.port = port
        self.connections = set()

    async def handle_connection(self, websocket, path):
        logger.info('Handling initial connection at path {}'.format(path))
        user_ctx = UserContext(websocket)
        logger.info('Registering user context {}'.format(user_ctx))
        self.connections.add(user_ctx)
        async for message in websocket:
            await self.handle_message(user_ctx, message)

    async def handle_message(self, user_ctx, message):
        logger.info("Handling message '{}' for {}".format(message, user_ctx))
        # TODO for now, just echo
        await user_ctx.websocket.send(message)

    def start(self):
        logger.info('Starting up asyncio loop')
        asyncio.get_event_loop().run_until_complete(
            ws.serve(self.handle_connection, self.bind, self.port))
        # TODO why two run invocations? docs don't explain.
        asyncio.get_event_loop().run_forever()
