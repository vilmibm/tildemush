import os, time
import asyncio
import json
import websockets
from tempfile import NamedTemporaryFile
import urwid

from .config import Config
from . import ui
from .ui import Screen, Form, FormField, menu, menu_button, sub_menu, ColorText, ExternalEditor

def quit_client(screen):
    # TODO: quit command isn't getting caught by the server for some
    # reason?
    asyncio.ensure_future(screen.client_state.send('COMMAND QUIT'), loop=screen.loop)

    raise urwid.ExitMainLoop()

class Splash(Screen):
    def __init__(self, exit=lambda _:True):
        bt = urwid.BigText('WELCOME TO TILDEMUSH', urwid.font.HalfBlock5x4Font())
        bt = urwid.Padding(bt, 'center', None)
        bt = urwid.Filler(bt, 'middle', None, 7)
        ftr = ColorText('~ press any key to jack in ~', align='center')
        self.base = urwid.Frame(body=bt, footer=ftr)
        super().__init__(self.base, exit=exit)

    def input(self, key):
        self.exit(True)


class MainMenu(Screen):
    def __init__(self, loop, client=None, exit=lambda _: True):
        self.loop = loop
        ftr = ColorText('press ESC to close windows', align='center')
        body = ui.solidfill('░', 'background')
        self.base = urwid.Frame(body=body, footer=ftr)
        super().__init__(self.base, client, exit)
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
                menu_button('exit', quit_client)]))

    def input(self, key):
        return False

    def show_login(self):
        un = self.client.config.get('username')
        pw = self.client.config.get('password')
        if un and pw:
            asyncio.wait_for(
                    asyncio.ensure_future(self.handle_login({'username':un, 'password':pw}), loop=self.loop),
                    60.0, loop=self.loop)
        else:
            un_field = FormField(caption='username: ', name='username')
            pw_field = FormField(caption='password: ', name='password', mask='~')
            submit_btn = urwid.Button('login! >')
            login_form = Form([un_field, pw_field], submit_btn)

            def wait_for_login(_):
                asyncio.wait_for(
                    asyncio.ensure_future(self.handle_login(login_form.data), loop=self.loop),
                    60.0, loop=self.loop)

            urwid.connect_signal(submit_btn, 'click', wait_for_login)

            self.open_box(urwid.Filler(login_form))

    async def handle_login(self, login_data):
        await self.client.authenticate(login_data['username'], login_data['password'])

    def show_register(self):
        info = ColorText('register a new account! password must be at least 12 characters long.\n')
        un_field = FormField(caption='username: ', name='username')
        pw_field = FormField(caption='password: ', name='password', mask='~')
        pw_confirm_field = FormField(caption='confirm password: ', name='confirm_password', mask='~')
        submit_btn = urwid.Button('register! >')
        register_form = Form([un_field, pw_field, pw_confirm_field], submit_btn)

        def wait_for_register(_):
            asyncio.wait_for(
                asyncio.ensure_future(self.handle_register(register_form.data), loop=self.loop),
                60.0, loop=self.loop)

        urwid.connect_signal(submit_btn, 'click', wait_for_register)
        self.open_box(urwid.Filler(urwid.Pile([info, register_form])))

    async def handle_register(self, register_data):
        if not register_data['username']:
            self.message("please enter a username", "error")
            return

        if not register_data['password']\
           or not register_data['confirm_password']\
           or register_data['password'] != register_data['confirm_password']:
            self.message("password mismatch", "error")
            return

        await self.client.register(register_data['username'], register_data['password'])

class GameMain(urwid.Frame):
    def __init__(self, client_state, loop, ui_loop, config):
        self.client_state = client_state
        self.loop = loop
        self.ui_loop = ui_loop
        self.config = config
        self.game_state = {"USER":{
                    "description": "a shadow",
                    "display_name": "nothing"},
                    "room": {
                        "name": "limbo",
                        "description": "a liminal space. type /look to open your eyes.",
                        "contains":[]}
                    }
        self.scope = []
        self.hotkeys = self.load_hotkeys()

        self.game_tab = ui.GameView(self.game_state)
        self.witch_tab = ui.WitchView({}, self.scope)
        self.worldmap_tab = ui.WorldmapView()
        self.settings_tab = ui.SettingsView()

        # quit placeholder
        self.quit_prompt = urwid.Edit()
        self.quit_view = ColorText("quit")
        self.quit_tab = ui.GameTab(self.quit_view,
                ui.TabHeader("F9 QUIT", position='last'), self.quit_prompt)

        # set starting conditions
        self.tabs = {
                "f1": self.game_tab,
                "f2": self.witch_tab,
                "f3": self.worldmap_tab,
                "f4": self.settings_tab,
                "f9": self.quit_tab
                }
        self.tab_headers = urwid.Columns([])
        self.header = self.tab_headers
        self.refresh_tabs()
        self.prompt = self.game_tab.prompt
        self.statusbar = ColorText("{dark green}connection okay!", align='right')
        self.client_state.set_on_recv(self.on_server_message)
        super().__init__(header=self.header, body=self.game_tab, footer=self.statusbar)
        self.focus_prompt()

    async def on_server_message(self, server_msg):
        if server_msg == 'COMMAND OK':
            pass
        elif server_msg.startswith('STATE'):
            self.update_state(server_msg[6:])
        elif server_msg.startswith('OBJECT'):
            object_state = json.loads(server_msg[7:])
            if object_state.get('edit'):
                self.launch_witch(object_state)
        else:
            self.game_tab.add_message(server_msg)

        self.focus_prompt()

    def launch_witch(self, data):
        tf = NamedTemporaryFile(delete=False, mode='w')
        tf.write(data["code"])
        tf.close()
        self.witch_tab.editor.original_widget = urwid.BoxAdapter(
                ExternalEditor(tf.name, self.ui_loop,
                    lambda path: self.close_witch(data, path)),
                self.ui_loop.screen_size[1] // 2
            )
        self.witch_tab.prompt = self.witch_tab.editor.original_widget
        self.witch_tab.refresh(data, self.scope)
        self.switch_tab(self.tabs.get("f2"))

    def close_witch(self, data, filepath):
        with open(filepath, "r") as f:
            code = f.read()
        revision_payload = dict(
            shortname=data["shortname"],
            code=code,
            current_rev=data["current_rev"])
        os.remove(filepath)

        self.witch_tab.editor.original_widget  = self.witch_tab.editor_filler
        self.switch_tab(self.tabs.get("f1"))

        payload = 'REVISION {}'.format(json.dumps(revision_payload))
        self.witch_tab.refresh({}, self.scope)
        asyncio.ensure_future(self.client_state.send(payload), loop=self.loop)

    def focus_prompt(self):
        self.focus_position = 'body'
        self.prompt = self.body.prompt

    def keypress(self, size, key):
        if key == 'enter' and self.prompt == self.game_tab.prompt:
            self.handle_game_input(self.prompt.get_edit_text())
        else:
            try:
                self.prompt.keypress((size[0],), key)
            except ValueError:
                pass
            self.handle_keypress(size, key)


    def handle_game_input(self, text):
        # TODO handle any validation of text
        self.prompt.add_line(text)

        if not self.client_state.listening:
            asyncio.ensure_future(self.client_state.start_listen_loop(), loop=self.loop)

        if text.startswith('/quit'):
            quit_client(self)
        elif text.startswith('/edit'):
            #TODO check for active witch editor
            text = text[1:]
        elif text.startswith('/'):
            text = text[1:]
        else:
            chat_color = self.config.get('chat_color', 'light magenta')
            if text:
                text = 'say {'+chat_color+'}'+text+'{/}'
            else:
                text = 'say {'+chat_color+'}...{/}'

        server_msg = 'COMMAND {}'.format(text)

        asyncio.ensure_future(self.client_state.send(server_msg), loop=self.loop)
        self.prompt.edit_text = ''

    def handle_keypress(self, size, key):
        # debugging output
        #self.footer = urwid.Text(key)

        if key in self.hotkeys.get("quit"):
            quit_client(self)
        elif key in self.tabs.keys():
            self.switch_tab(self.tabs.get(key))
        elif key in self.hotkeys.get("scrolling").keys():
            if self.body == self.game_tab:
                self.game_text.keypress(size, key)
        elif key in self.hotkeys.get("movement").keys():
            asyncio.ensure_future(self.client_state.send(
                    "COMMAND {}".format(self.hotkeys.get("movement").get(key))
                ), loop=self.loop)
        elif key in self.hotkeys.get("rlwrap").keys() and isinstance(self.prompt, ui.GamePrompt):
            self.prompt.handle_rlwrap(self.hotkeys.get("rlwrap").get(key))

    def switch_tab(self, new_tab):
        self.body.unfocus()
        self.body = new_tab
        self.body.focus()
        self.focus_prompt()
        self.refresh_tabs()

    def refresh_tabs(self):
        headers = []
        for tab in sorted(self.tabs.keys()):
            headers.append(self.tabs.get(tab).tab_header)
        self.tab_headers = urwid.Columns(headers)
        self.header = self.tab_headers

    def update_state(self, raw_state):
        self.game_state = json.loads(raw_state)
        self.update_scope()
        self.game_tab.refresh(self.game_state)
        self.witch_tab.refresh(self.game_state, self.scope)

    def update_scope(self):
        self.scope.clear()
        for o in self.game_state.get("room").get("contains"):
            self.scope.append(o.get("shortname"))
        for o in self.game_state.get("inventory"):
            self.scope.append(o.get("shortname"))

    def load_hotkeys(self):
        defaults = {
                "scrolling": {
                    "page up": "up",
                    "page down": "down",
                    },
                "quit": [
                    "f9"
                    ],
                "movement": {
                    "shift up": "go north",
                    "shift down": "go south",
                    "shift left": "go west",
                    "shift right": "go east",
                    "shift page up": "go above",
                    "shift page down": "go below",
                    },
                "rlwrap": {
                    "up": "up",
                    "down": "down",
                    "ctrl a": "start",
                    "ctrl e": "end",
                    "ctrl u": "delete backwards",
                    "ctrl k": "delete forwards"
                    }
                }

        hotkeys = {}
        for group in defaults:
            hotkeys.update({group: self.config.get(group, defaults.get(group))})
        return hotkeys
