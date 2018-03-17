import asyncio
import copy
import json
import os

import urwid
import websockets

DEFAULT_CONFIG_PATH = os.path.expanduser('~/.config/tildemush/config.json')

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

    @property
    def login_url(self):
        return 'ws://{host}:{port}'.format(
            host=self.config.get('server_host'),
            port=self.config.get('server_port'))

    def connect(self):
        print('GON CONNECT')
        print(self.login_url)
        self.connection = websockets.connect(self.login_url)

    def authenticate(self, username, password):
        print('HAHAHAHAHAHAHAHAHA {} {}'.format(username, password))
        if self.connection is None:
            self.connect()
        self.connection.send('AUTH {}:{}'.format(username, password))
        auth_response = websocket.recv()
        if auth_response != 'AUTH OK':
            raise Exception('TODO better error for failing to login: {}'.format(auth_response))
        self.authenticated = True

    async def send(self, text):
        await self.connection.send(text)


class Form(urwid.Pile):
    def __init__(self, fields, submit, on_submit):
        super().__init__(fields+[submit])
        self.fields = fields
        self.submit_btn = submit
        self.on_submit = on_submit

        urwid.connect_signal(self.submit_btn, 'click', self.submit)


    def submit(self, _):
        data = {}
        for w in self.fields:
            data[w.name] = w.get_edit_text()

        self.on_submit(data)


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
    login_form = Form(fields=[un_field, pw_field],
                      submit=submit_btn,
                      on_submit=handle_login)

    TOP.open_box(urwid.Filler(login_form))

def handle_login(login_data):
    CLIENT_STATE.authenticate(login_data['username'], login_data['password'])
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
        super(CascadingBoxes, self).__init__(initial)
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


bt = urwid.BigText('WELCOME TO TILDEMUSH', urwid.font.HalfBlock7x7Font())
bt = urwid.Padding(bt, 'center', None)
bt = urwid.Filler(bt, 'middle', None, 7)
ftr = urwid.Text('~ press any key to jack in ~', align='center')
f = urwid.Frame(body=bt, footer=ftr)
SPLASH = f

TOP = CascadingBoxes(menu_top, SPLASH)
CLIENT_STATE = ClientState()
game_main_hdr = urwid.Text('welcome 2 tildemush, u are jacked in')
game_main_bdy = urwid.Columns([
    urwid.Filler(urwid.Text('lol game stuff happens here')),
    urwid.Pile([
        urwid.Filler(urwid.Text('details about your current room')),
        urwid.Filler(urwid.Text('i donno a map?')),
        urwid.Filler(urwid.Text('character info'))
    ])


], dividechars=1)
game_main_ftr = urwid.Edit(caption='> ', multiline=True)
GAME_MAIN = urwid.Frame(header=game_main_hdr, body=game_main_bdy, footer=game_main_ftr)

def start():
    evl = urwid.AsyncioEventLoop(loop=asyncio.get_event_loop())
    urwid.MainLoop(TOP, event_loop=evl, palette=[('reversed', 'standout', '')]).run()
