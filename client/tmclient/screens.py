import os, time
import asyncio
import json
import websockets
import urwid

from .config import Config
from . import ui
from .ui import Screen, Form, FormField, menu, menu_button, sub_menu

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
        ftr = urwid.Text('~ press any key to jack in ~', align='center')
        self.base = urwid.Frame(body=bt, footer=ftr)
        super().__init__(self.base, exit=exit)

    def input(self, key):
        self.exit(True)


class MainMenu(Screen):
    def __init__(self, loop, client=None, exit=lambda _: True):
        self.loop = loop
        ftr = urwid.Text('press ESC to close windows', align='center')
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
        info = urwid.Text('register a new account! password must be at least 12 characters long.\n')
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


class GamePrompt(urwid.Edit):
    def __init__(self):
        super().__init__(caption='> ', multiline=True)


class GameMain(urwid.Frame):
    def __init__(self, client_state, loop):
        self.client_state = client_state
        self.loop = loop
        self.state = {"user":{
                    "description": "a shadow",
                    "display_name": "nothing"},
                    "room": {
                        "name": "limbo",
                        "description": "a liminal space. type /look to open your eyes.",
                        "contains":[]}
                    }
        self.hotkeys = self.load_hotkeys()

        # game view stuff
        self.game_walker = urwid.SimpleFocusListWalker([
            urwid.Text('you have reconstituted into tildemush')
            ])
        self.game_text = urwid.ListBox(self.game_walker)
        self.here_text = urwid.Pile(self.here_info())
        self.user_text = urwid.Pile(self.user_info())
        self.minimap_text = urwid.Text("MAP", align='center')
        self.main_body = urwid.Columns([
            self.game_text,
            urwid.Pile([
                ui.DashedBox(urwid.Filler(self.here_text, valign='top')),
                ui.DashedBox(urwid.Filler(self.minimap_text, valign='middle')),
                ui.DashedBox(urwid.Filler(self.user_text, valign='top'))
            ])
        ])
        self.main_banner = urwid.Text('====welcome 2 tildemush, u are jacked in====')
        self.main_prompt = GamePrompt()
        self.main_view = urwid.Frame(header=self.main_banner,
                body=self.main_body, footer=self.main_prompt)
        self.main_view.focus_position = 'footer'

        self.main_tab = ui.GameTab(self.main_view,
                ui.TabHeader("F1 MAIN", position='first',
                    selected=True), self.main_prompt)

        # witch view stuff
        self.witch_prompt = urwid.Edit()
        self.witch_view= urwid.Filler(urwid.Text("witch editor in progress", align='center'), valign='middle')
        self.witch_tab = ui.GameTab(self.witch_view,
                ui.TabHeader("F2 WITCH"), self.witch_prompt)

        # worldmap view stuff
        self.worldmap_prompt = urwid.Edit()
        self.worldmap_view = urwid.Filler(urwid.Text("worldmap coming soon", align='center'), valign='middle')
        self.worldmap_tab = ui.GameTab(self.worldmap_view,
                ui.TabHeader("F3 WORLDMAP"), self.worldmap_prompt)

        # settings view stuff
        self.settings_prompt = urwid.Edit()
        self.settings_view = urwid.Filler(urwid.Text("settings menu under construction", align='center'), valign='middle')
        self.settings_tab = ui.GameTab(self.settings_view,
                ui.TabHeader("F4 SETTINGS"), self.settings_prompt)

        # quit placeholder
        self.quit_prompt = urwid.Edit()
        self.quit_view = self.main_view
        self.quit_tab = ui.GameTab(self.quit_view,
                ui.TabHeader("F9 QUIT", position='last'), self.quit_prompt)

        # set starting conditions
        self.tabs = {
                "f1": self.main_tab,
                "f2": self.witch_tab,
                "f3": self.worldmap_tab,
                "f4": self.settings_tab,
                "f9": self.quit_tab
                }
        self.tab_headers = urwid.Columns([])
        self.header = self.tab_headers
        self.refresh_tabs()
        self.prompt = self.main_prompt
        self.statusbar = urwid.Text("connection okay!", align='right')
        self.client_state.set_on_recv(self.on_server_message)
        super().__init__(header=self.header, body=self.main_tab, footer=self.statusbar)
        self.focus_prompt()

    async def on_server_message(self, server_msg):
        if server_msg == 'COMMAND OK':
            pass
        elif server_msg.startswith('STATE'):
            self.update_state(server_msg[6:])
        else:
            self.game_walker.append(urwid.Text(server_msg))
            self.game_walker.set_focus(len(self.game_walker)-1)

        self.focus_prompt()

    def focus_prompt(self):
        self.focus_position = 'body'
        self.prompt = self.body.prompt

    def keypress(self, size, key):
        if key == 'enter':
            if self.prompt == self.main_tab.prompt:
                self.handle_game_input(self.prompt.get_edit_text())
            else:
                self.prompt.edit_text = ''
        else:
            self.prompt.keypress((size[0],), key)
            self.handle_keypress(size, key)

    def handle_game_input(self, text):
        # TODO handle any validation of text
        if not self.client_state.listening:
            asyncio.ensure_future(self.client_state.start_listen_loop(), loop=self.loop)

        if text.startswith('/quit'):
            quit_client(self)
        elif text.startswith('/'):
            text = text[1:]
        else:
            text = 'say {}'.format(text)

        server_msg = 'COMMAND {}'.format(text)

        asyncio.ensure_future(self.client_state.send(server_msg), loop=self.loop)
        self.prompt.edit_text = ''

    def handle_keypress(self, size, key):
        # debugging output
        #self.footer = urwid.Text(key)

        if key in self.hotkeys.get("quit"):
            quit_client(self)
        elif key in self.tabs.keys():
            # tab switcher
            self.body.unfocus()
            self.body = self.tabs.get(key)
            self.body.focus()
            self.focus_prompt()
            self.refresh_tabs()
        elif key in self.hotkeys.get("scrolling"):
            if self.body == self.main_tab:
                self.game_text.keypress(size, key)

    def refresh_tabs(self):
        headers = []
        for tab in sorted(self.tabs.keys()):
            headers.append(self.tabs.get(tab).tab_header)
        self.tab_headers = urwid.Columns(headers)
        self.header = self.tab_headers

    def update_state(self, raw_state):
        self.state = json.loads(raw_state)
        self.here_text.contents.clear()
        self.user_text.contents.clear()

        # TODO: this is kind of hardcoded for the current three-widget
        # here_info() and two-widget user_info()

        self.here_text.contents.extend(list(
            zip(self.here_info(),
                [self.here_text.options(),
                    self.here_text.options(),
                    self.here_text.options()]
                )
            ))

        self.user_text.contents.extend(list(
            zip(self.user_info(),
                [self.here_text.options(),
                    self.here_text.options()]
                )
            ))

    def here_info(self):
        room = self.state.get("room", {})
        info = "[{}]".format(room.get("name"))
        contents = []
        if len(room.get("contains", [])) < 2:
            contents.append("no one but yourself")
        else:
            for o in room.get("contains"):
                contents.append(o.name)

        lines = [
                urwid.Text("[{}]".format(room.get("name")), align='center'),
                urwid.Text("{}\n".format(room.get("description"))),
                urwid.Text("You see here ({pop}): {contents}".format(
                    pop=len(contents), contents=', '.join(contents)))
                ]

        return lines

    def user_info(self):
        user = self.state.get("user", {})
        inventory = []

        for item in self.state.get("inventory", []):
            inventory.append(item.get("name"))

        lines = [
                urwid.Text("<{desc} named {name}>\n".format(
                desc=user.get("description"),
                name=user.get("display_name")), align='center'),
                urwid.Text("Inventory ({count}): {inv}".format(
                    count=len(inventory),
                    inv=", ".join(inventory)))
                ]

        return lines

    def load_hotkeys(self):
        # TODO: defaults are listed here, but this should also eventually
        # load user's custom keybindings/overrides
        hotkeys = {
                "scrolling": {
                    "page up": "up",
                    "page down": "down",
                    "up": "up",
                    "down": "down"
                    },
                "quit": [
                    "f9"
                    ]
                }

        return hotkeys
