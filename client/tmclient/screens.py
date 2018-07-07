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


class GamePrompt(urwid.Edit):
    def __init__(self):
        super().__init__(caption='> ', multiline=True)


class GameMain(urwid.Frame):
    def __init__(self, client_state, loop, ui_loop):
        self.client_state = client_state
        self.loop = loop
        self.ui_loop = ui_loop
        self.state = {"user":{
                    "description": "a shadow",
                    "display_name": "nothing"},
                    "room": {
                        "name": "limbo",
                        "description": "a liminal space. type /look to open your eyes.",
                        "contains":[]}
                    }
        self.scope = []
        self.hotkeys = self.load_hotkeys()
        self.input_history = [""]
        self.input_index = 0

        # game view stuff
        self.game_walker = urwid.SimpleFocusListWalker([
            ColorText('{yellow}you have reconstituted into tildemush'),
            ColorText("")
            ])
        self.game_text = urwid.ListBox(self.game_walker)
        self.here_text = urwid.Pile(self.here_info())
        self.user_text = urwid.Pile(self.user_info())
        self.minimap_grid = urwid.Pile(self.generate_minimap())
        self.main_body = urwid.Columns([
            self.game_text,
            urwid.Pile([
                ui.DashedBox(urwid.Filler(self.here_text, valign='top')),
                ui.DashedBox(urwid.Filler(self.minimap_grid, valign='middle')),
                ui.DashedBox(urwid.Filler(self.user_text, valign='top'))
            ])
        ])
        self.main_banner = ColorText('====welcome 2 tildemush, u are jacked in====')
        self.main_prompt = GamePrompt()
        self.main_view = urwid.Frame(header=self.main_banner,
                body=self.main_body, footer=self.main_prompt)
        self.main_view.focus_position = 'footer'

        self.main_tab = ui.GameTab(self.main_view,
                ui.TabHeader("F1 MAIN", position='first',
                    selected=True), self.main_prompt)

        # witch view stuff
        self.witch_tab = ui.WitchView({})

        # worldmap view stuff
        self.worldmap_prompt = urwid.Edit()
        self.worldmap_view = urwid.Filler(ColorText("worldmap coming soon", align='center'), valign='middle')
        self.worldmap_tab = ui.GameTab(self.worldmap_view,
                ui.TabHeader("F3 WORLDMAP"), self.worldmap_prompt)

        # settings view stuff
        self.settings_prompt = urwid.Edit()
        self.settings_view = urwid.Filler(ColorText("settings menu under construction", align='center'), valign='middle')
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
        self.statusbar = ColorText("{dark green}connection okay!", align='right')
        self.client_state.set_on_recv(self.on_server_message)
        super().__init__(header=self.header, body=self.main_tab, footer=self.statusbar)
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
            self.add_game_message(server_msg)

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
        asyncio.ensure_future(self.client_state.send(payload), loop=self.loop)

    def focus_prompt(self):
        self.focus_position = 'body'
        self.prompt = self.body.prompt

    def keypress(self, size, key):
        if key == 'enter' and self.prompt == self.main_tab.prompt:
            self.handle_game_input(self.prompt.get_edit_text())
        else:
            try:
                self.prompt.keypress((size[0],), key)
            except ValueError:
                pass
            self.handle_keypress(size, key)

    def add_game_message(self, msg):
        spacer = self.game_walker.pop()
        self.game_walker.append(ColorText(msg))
        self.game_walker.append(spacer)
        self.game_walker.set_focus(len(self.game_walker)-1)

    def handle_game_input(self, text):
        # TODO handle any validation of text
        blank = self.input_history.pop()
        self.input_history.append(text)
        self.input_history.append(blank)
        self.input_index += 1

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
            chat_color = self.client_state.config.get('chat_color') or 'light magenta'
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
            if self.body == self.main_tab:
                self.game_text.keypress(size, key)
        elif key in self.hotkeys.get("movement").keys():
            asyncio.ensure_future(self.client_state.send(
                    "COMMAND {}".format(self.hotkeys.get("movement").get(key))
                ), loop=self.loop)
        elif key in self.hotkeys.get("rlwrap").keys():
            #self.get("rlwrap").get("key")
            self.handle_rlwrap(self.hotkeys.get("rlwrap").get(key))

    def handle_rlwrap(self, key):
        rlwrap_map = {
                "up": self.rlwrap_up,
                "down": self.rlwrap_down,
                "start": self.rlwrap_start,
                "end": self.rlwrap_end,
                "delete backwards": self.rlwrap_delete_backwards,
                "delete forwards": self.rlwrap_delete_forwards
                }

        rlwrap_map.get(key)()

    def rlwrap_up(self):
        self.input_index = max(0, self.input_index - 1)
        self.prompt.edit_text = self.input_history[self.input_index]
        self.prompt.set_edit_pos(len(self.prompt.edit_text))

    def rlwrap_down(self):
        self.input_index = min(len(self.input_history) - 1, self.input_index + 1)
        self.prompt.edit_text = self.input_history[self.input_index]
        self.prompt.set_edit_pos(len(self.prompt.edit_text))

    def rlwrap_start(self):
        self.prompt.set_edit_pos(0)

    def rlwrap_end(self):
        self.prompt.set_edit_pos(len(self.prompt.edit_text))

    def rlwrap_delete_backwards(self):
        self.prompt.edit_text = self.prompt.edit_text[self.prompt.edit_pos:]
        self.rlwrap_start()

    def rlwrap_delete_forwards(self):
        self.prompt.edit_text = self.prompt.edit_text[0:self.prompt.edit_pos]
        self.rlwrap_end()

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
        self.state = json.loads(raw_state)
        self.scope.clear()
        for o in self.state.get("room").get("contains"):
            self.scope.append(o.get("shortname"))
        for o in self.state.get("inventory"):
            self.scope.append(o.get("shortname"))
        self.here_text.contents.clear()
        self.user_text.contents.clear()
        self.minimap_grid.contents.clear()

        # TODO: this is kind of hardcoded for the current three-widget
        # here_info(), two-widget user_info(), three-widget generate_minimap()

        self.here_text.contents.extend(list(
            zip(self.here_info(),
                [self.here_text.options(),
                    self.here_text.options(),
                    self.here_text.options()]
                )
            ))

        self.user_text.contents.extend(list(
            zip(self.user_info(),
                [self.user_text.options(),
                    self.user_text.options()]
                )
            ))

        self.minimap_grid.contents.extend(list(
            zip(self.generate_minimap(),
                [self.minimap_grid.options(),
                    self.minimap_grid.options(),
                    self.minimap_grid.options()]
                )
            ))


    def here_info(self):
        room = self.state.get("room", {})
        info = "[{}]".format(room.get("name"))
        contents = []
        if len(room.get("contains", [])) < 1:
            contents.append("no one but yourself")
        else:
            for o in room.get("contains"):
                contents.append(o.get("name"))

        lines = [
                ColorText("[{}]".format(room.get("name")), align='center'),
                ColorText("{}\n".format(room.get("description"))),
                ColorText("You see here ({pop}): {contents}\n".format(
                    pop=len(contents), contents=', '.join(contents)))
                ]

        return lines

    def user_info(self):
        user = self.state.get("user", {})
        inventory = []

        for item in self.state.get("inventory", []):
            inventory.append(item.get("name"))

        lines = [
                ColorText("<{desc} named {name}>\n".format(
                desc=user.get("description"),
                name=user.get("display_name")), align='center'),
                ColorText("Inventory ({count}): {inv}".format(
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

        return hotkeys

    def generate_minimap(self):
        """Generates a minimap for the cardinal exits of the current room."""
        room = self.state.get("room", {})
        exits = room.get("exits", {})
        blank = urwid.LineBox(urwid.Text(" "),
                tlcorner=' ', tline=' ', lline=' ', trcorner=' ', blcorner=' ',
                rline=' ', bline=' ', brcorner=' '
        )
        map_nodes = {
                "north": blank,
                "east": blank,
                "south": blank,
                "west": blank,
                "above": blank,
                "below": blank,
                }

        for direction in exits.keys():
            target = exits.get(direction)
            node = urwid.LineBox(urwid.Text(target.get("room_name", "(somewhere)"), align='center'))
            map_nodes.update({direction: node})

        map_grid = [
                urwid.Columns([
                    map_nodes.get("above"),
                    map_nodes.get("north"),
                    urwid.Text(" ")
                    ]),
                urwid.Columns([
                    map_nodes.get("west"),
                    urwid.LineBox(urwid.Text(room.get("name", "somewhere"), align='center')),
                    map_nodes.get("east")
                    ]),
                urwid.Columns([
                    urwid.Text(" "),
                    map_nodes.get("south"),
                    map_nodes.get("below")
                    ])
                ]

        return map_grid
