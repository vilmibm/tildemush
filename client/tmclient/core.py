import asyncio
import copy
import json
import os

import urwid
import websockets

DEFAULT_CONFIG_PATH = os.path.expanduser('~/.config/tildemush/config.json')
LOOP = asyncio.get_event_loop()
ULOOP = urwid.AsyncioEventLoop(loop=LOOP)

# TODO handle actually creating DEFAULT_CONFIG_PATH
CONFIG_DEFAULTS = {'todo':'todo'}

class Config:
    def __init__(self, path=DEFAULT_CONFIG_PATH):
        self.path = path
        self._data = CONFIG_DEFAULTS
        self.read()

    def read(self):
        self._data = CONFIG_DEFAULTS

        file_config = None
        with open(self.path) as config_file:
            file_config = json.loads(config_file.read())

        for k,v in file_config.items():
            self._data[k] = v

    def set_path(self, new_path):
        self.path = new_path
        self.read()

    def get(self, key):
        return self._data.get(key)


    def set(self, key, value):
        self._data[key] = value
        self.sync()

    def sync(self):
        with open(self.path, 'w') as config_file:
            config_file.write(json.dumps(self._data), sort_keys=True, indent=4)


class ClientState:
    def __init__(self):
        self.connection = None
        self.config = Config()
        self.listening = False

    @property
    def login_url(self):
        return 'ws://{host}:{port}'.format(
            host=self.config.get('server_host'),
            port=self.config.get('server_port'))

    def set_on_recv(self, handler):
        self.recv_handler = handler

    async def connect(self):
        print('GON CONNECT')
        print(self.login_url)
        self.connection = await websockets.connect(self.login_url)

    async def start_listen_loop(self):
        self.listening = True
        async for server_msg in self.connection:
            await self.recv_handler(server_msg)

    async def authenticate(self, username, password):
        print('LOL {} {}'.format(username, password))
        if self.connection is None:
            await self.connect()
        await self.connection.send('AUTH {}:{}'.format(username, password))
        auth_response = await self.connection.recv()
        if auth_response != 'AUTH OK':
            raise Exception('TODO better error for failing to login: {}'.format(auth_response))
        self.authenticated = True

    async def send(self, text):
        await self.connection.send(text)


class Form(urwid.Pile):
    def __init__(self, fields, submit):
        super().__init__(fields+[submit])
        self.fields = fields
        self.submit_btn = submit

    @property
    def data(self):
        data = {}
        for w in self.fields:
            data[w.name] = w.get_edit_text()
        return data


class FormField(urwid.Edit):
    def __init__(self, *args, **kwargs):
        name = kwargs.get('name')
        del kwargs['name']
        super().__init__(*args, **kwargs)
        self.name = name

def menu_button(caption, callback):
    button = urwid.Button(caption)
    urwid.connect_signal(button, 'click', callback)
    return urwid.AttrMap(button, None, focus_map='reversed')

def sub_menu(caption, choices):
    contents = menu(caption, choices)
    def open_menu(button):
        return TOP.open_box(contents)
    return menu_button([caption, u'...'], open_menu)

def menu(title, choices):
    body = [urwid.Text(title), urwid.Divider()]
    body.extend(choices)
    return urwid.ListBox(urwid.SimpleFocusListWalker(body))

def item_chosen(button):
    response = urwid.Text([u'You chose ', button.label, u'\n'])
    done = menu_button(u'Ok', exit_program)
    TOP.open_box(urwid.Filler(urwid.Pile([response, done])))

def exit_program(button):
    raise urwid.ExitMainLoop()

def show_login(_):
    # TODO if un and pw are in config, use that and skip showing this
    un_field = FormField(caption='username: ', name='username')
    pw_field = FormField(caption='password: ', name='password', mask='~')
    submit_btn = urwid.Button('login! >')
    login_form = Form([un_field, pw_field], submit_btn)

    def wait_for_login(_):
        asyncio.wait_for(
            asyncio.ensure_future(handle_login(login_form.data), loop=LOOP),
            60.0, loop=LOOP)

    urwid.connect_signal(submit_btn, 'click', wait_for_login)

    TOP.open_box(urwid.Filler(login_form))

async def handle_login(login_data):
    await CLIENT_STATE.authenticate(login_data['username'], login_data['password'])
    TOP.original_widget = GAME_MAIN

def handle_exit(_):
    raise urwid.ExitMainLoop()


# TODO dynamically create the main menu based on authentication state
menu_top = menu('tildemush main menu', [
    menu_button('login', show_login),
    sub_menu('create a new user account', [
        menu_button('TODO', item_chosen),
    ]),
    sub_menu('settings', [
        menu_button('forget login details', item_chosen),
        menu_button('set server domain', item_chosen),
        menu_button('set server port', item_chosen),
        menu_button('set server password', item_chosen)
    ]),
    menu_button('exit', handle_exit)
])


class SplashScreen(urwid.BigText):
    def __init__(self):
        super(SplashScreen, self).__init__('welcome to\ntildemush',
                                           urwid.font.HalfBlockHeavy6x5Font())

class CascadingBoxes(urwid.WidgetPlaceholder):
    max_box_levels = 4

    def __init__(self, box, initial):
        super().__init__(initial)
        self.box_level = 0
        self.box = box
        self.initial = initial

    def open_box(self, box):
        self.original_widget = urwid.Overlay(urwid.LineBox(box),
            self.original_widget,
            align='center', width=('relative', 80),
            valign='middle', height=('relative', 80),
            min_width=24, min_height=8,
            left=self.box_level * 3,
            right=(self.max_box_levels - self.box_level - 1) * 3,
            top=self.box_level * 2,
            bottom=(self.max_box_levels - self.box_level - 1) * 2)
        self.box_level += 1

    def keypress(self, size, key):
        if self.original_widget is self.initial:
            self.original_widget = urwid.SolidFill('~')
            self.open_box(self.box)
        elif key == 'esc' and self.box_level > 1:
            self.original_widget = self.original_widget[0]
            self.box_level -= 1
        else:
            return super(CascadingBoxes, self).keypress(size, key)

class GamePrompt(urwid.Edit):
    def __init__(self):
        super().__init__(caption='> ', multiline=True)

class GameMain(urwid.Frame):
    def __init__(self, client_state, loop):
        self.client_state = client_state
        self.loop = loop
        self.banner = urwid.Text('welcome 2 tildemush, u are jacked in')
        self.game_text = urwid.Text('lol game stuff happens here')
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
        self.game_text.set_text("{}\n{}".format(
            self.game_text.get_text(),
            server_msg))

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
        asyncio.ensure_future(self.client_state.send(text), loop=self.loop)
        self.prompt.edit_text = ''


bt = urwid.BigText('WELCOME TO TILDEMUSH', urwid.font.HalfBlock7x7Font())
bt = urwid.Padding(bt, 'center', None)
bt = urwid.Filler(bt, 'middle', None, 7)
ftr = urwid.Text('~ press any key to jack in ~', align='center')
f = urwid.Frame(body=bt, footer=ftr)
SPLASH = f

TOP = CascadingBoxes(menu_top, SPLASH)
CLIENT_STATE = ClientState()
GAME_MAIN = GameMain(client_state=CLIENT_STATE, loop=LOOP)


def start():
    urwid.MainLoop(TOP, event_loop=ULOOP, palette=[('reversed', 'standout', '')]).run()
