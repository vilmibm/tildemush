import os, time
import asyncio
import json
import websockets
import urwid

from .config import Config
from . import ui
from .ui import Screen, Form, FormField, menu, menu_button, sub_menu
from .screens import Splash, MainMenu, GameMain

class Client:
    def __init__(self, loop):
        self.loop = loop
        self.connection = None
        self.config = Config()
        self.ui = ui.UI(self.loop)
        self.listening = False
        self.authenticated = False
        self.ui.base = urwid.Overlay(
            urwid.Filler(urwid.Text('connecting..', align='center')),
            ui.solidfill('░', 'background'),
            align='center', width=15,
            valign='middle', height=3,)

    def run(self):
        asyncio.wait_for(asyncio.ensure_future(self.connect(), loop=self.loop),60.0, loop=self.loop)
        self.loop.run()

    def show_menu(self):
        self.ui.base = MainMenu(self.loop, client=self)

    @property
    def login_url(self):
        return 'ws://{host}:{port}'.format(
            host=self.config.get('server_host'),
            port=self.config.get('server_port'))

    def set_on_recv(self, handler):
        self.recv_handler = handler

    async def connect(self):
        self.connection = await websockets.connect(self.login_url)
        time.sleep(0.3) # people love to wait
        self.ui.base = Splash(lambda _:self.show_menu())

    async def start_listen_loop(self):
        self.listening = True
        async for server_msg in self.connection:
            await self.recv_handler(server_msg)

    async def authenticate(self, username, password):
        await self.connection.send('LOGIN {}:{}'.format(username, password))
        response = await self.connection.recv()
        if response == 'LOGIN OK':
            self.authenticated = True
            self.ui.base = GameMain(self, self.loop)
        else:
            self.ui.base.message(response, 'error')

    async def register(self, username, password):
        await self.connection.send('REGISTER {}:{}'.format(username, password))
        response = await self.connection.recv()
        if response == 'REGISTER OK':
            self.config.set('username', username)
            self.config.set('password', password)
            self.config.sync()
            self.ui.base.close_box()
            self.ui.base.show_login()
            self.ui.base.message("Account created!")
        else:
            self.ui.base.message(response, 'error')

    async def send(self, text):
        await self.connection.send(text)
