import os, time
import asyncio
import json
import websockets
import urwid

from .config import Config
from . import ui
from .ui import Screen, Form, FormField, menu, menu_button, sub_menu

LOOP = asyncio.get_event_loop()
CLIENT = None


def quit(_):
    raise urwid.ExitMainLoop()

class Client:
    def __init__(self):
        global CLIENT
        CLIENT = self
        self.connection = None
        self.config = Config()
        self.ui = ui.UI(LOOP)
        self.listening = False
        self.authenticated = False
        self.ui.base = urwid.Overlay(
            urwid.Filler(urwid.Text('connecting..', align='center')),
            ui.solidfill('░', 'background'),
            align='center', width=15,
            valign='middle', height=3,)
        asyncio.wait_for(asyncio.ensure_future(self.connect(), loop=LOOP),60.0, loop=LOOP)
        self.ui.loop.run()
        
    
    def show_menu(self):
        self.ui.base = MainMenu()

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
            self.ui.base = GameMain(self, LOOP)
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


class Splash(Screen):
    def __init__(self, exit=lambda _:True):    
        bt = urwid.BigText('WELCOME TO TILDEMUSH', urwid.font.HalfBlock5x4Font())
        bt = urwid.Padding(bt, 'center', None)
        bt = urwid.Filler(bt, 'middle', None, 7)
        ftr = urwid.Text('~ press any key to jack in ~', align='center')
        self.base = urwid.Frame(body=bt, footer=ftr)
        super().__init__(self.base, exit)

    def input(self, key):
        self.exit(True)

class MainMenu(Screen):
    def __init__(self, exit=lambda _:True):    
        self.base = ui.solidfill('░', 'background')
        super().__init__(self.base, exit)
        self.show_menu()

    def show_menu(self):
        self.open_box(
            menu('tildemush main menu', [
                menu_button('login', lambda _:self.show_login()),
                menu_button('create a new user account', lambda _:self.show_register()),
                sub_menu(self, 'settings', [
                    menu_button('forget login details', lambda _:True),
                    menu_button('set server domain', lambda _:True),
                    menu_button('set server port', lambda _:True),
                    menu_button('set server password', lambda _:True)]),
                menu_button('exit', quit)]))

    def input(self, key):
        return False

    def show_login(self):
        un = CLIENT.config.get('username')
        pw = CLIENT.config.get('password')
        if un and pw:
            asyncio.wait_for(
                    asyncio.ensure_future(self.handle_login({'username':un, 'password':pw}), loop=LOOP),
                    60.0, loop=LOOP)
        else:
            un_field = FormField(caption='username: ', name='username')
            pw_field = FormField(caption='password: ', name='password', mask='~')
            submit_btn = urwid.Button('login!')
            login_form = Form([un_field, pw_field], submit_btn)
            
            def wait_for_login(_):
                asyncio.wait_for(
                    asyncio.ensure_future(self.handle_login(login_form.data), loop=LOOP),
                    60.0, loop=LOOP)

            urwid.connect_signal(submit_btn, 'click', wait_for_login)

            self.open_box(urwid.Filler(login_form))

    async def handle_login(self, login_data):
        await CLIENT.authenticate(login_data['username'], login_data['password'])

    def show_register(self):
        un_field = FormField(caption='username: ', name='username')
        pw_field = FormField(caption='password: ', name='password', mask='~')
        pw_confirm_field = FormField(caption='confirm password: ', name='confirm_password', mask='~')
        submit_btn = urwid.Button('register! >')
        register_form = Form([un_field, pw_field, pw_confirm_field], submit_btn)

        def wait_for_register(_):
            asyncio.wait_for(
                asyncio.ensure_future(self.handle_register(register_form.data), loop=LOOP),
                60.0, loop=LOOP)

        urwid.connect_signal(submit_btn, 'click', wait_for_register)
        self.open_box(urwid.Filler(register_form))

    async def handle_register(self, register_data):
        if not register_data['username']:
            self.message("please enter a username", "error")
            return

        if not register_data['password']\
           or not register_data['confirm_password']\
           or register_data['password'] != register_data['confirm_password']:
            self.message("password mismatch", "error")
            return

        await CLIENT.register(register_data['username'], register_data['password'])





class GamePrompt(urwid.Edit):
    def __init__(self):
        super().__init__(caption='> ', multiline=True)

class GameMain(urwid.Frame):
    def __init__(self, client_state, loop):
        self.client_state = client_state
        self.loop = loop
        self.banner = urwid.Text('welcome 2 tildemush, u are jacked in')
        self.game_text = urwid.Pile([urwid.Text('lol game stuff happens here')])
        self.main = urwid.Columns([
            urwid.Filler(self.game_text),
            urwid.Pile([
                urwid.Filler(urwid.Text('details about your current room')),
                urwid.Filler(urwid.Text('i donno a map?')),
                urwid.Filler(urwid.Text('character info'))
            ])
        ], dividechars=1)
        self.prompt = GamePrompt()
        self.client_state.set_on_recv(self.on_server_message)
        super().__init__(header=self.banner, body=self.main, footer=self.prompt)
        self.focus_prompt()

    async def on_server_message(self, server_msg):
        self.game_text.contents.append(
            (urwid.Text(server_msg), self.game_text.options()))

    def focus_prompt(self):
        self.focus_position = 'footer'

    def keypress(self, size, key):
        if self.focus is self.prompt:
            if key == 'enter':
                self.handle_game_input(self.prompt.get_edit_text())
            else:
                self.prompt.keypress((size[0],), key)

    def handle_game_input(self, text):
        # TODO handle any validation of text
        if not self.client_state.listening:
            asyncio.ensure_future(self.client_state.start_listen_loop(), loop=self.loop)

        if text.startswith('/'):
            text = text[1:]
        else:
            text = 'say {}'.format(text)

        server_msg = 'COMMAND {}'.format(text)

        asyncio.ensure_future(self.client_state.send(server_msg), loop=self.loop)
        self.prompt.edit_text = ''