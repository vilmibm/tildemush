import os, time
import asyncio
import json
import websockets
import urwid

from .config import Config
from . import ui
from .ui import Screen, Form, FormField, menu, menu_button, sub_menu

def quit_client(_):
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
        # TODO: get room and user info passed in on init?
        self.room = {}
        self.user = {}

        # game view stuff
        self.game_walker = urwid.SimpleListWalker([
            urwid.Text('you have reconstituted into tildemush')
            ])
        self.game_text = urwid.ListBox(self.game_walker)
        self.here_text = urwid.Pile([urwid.Text(self.here_info())])
        self.user_text = urwid.Pile([urwid.Text(self.user_info())])
        self.minimap_text = urwid.Pile([urwid.Text("MAP")])
        self.world_body = urwid.Columns([
            self.game_text,
            urwid.Pile([
                ui.DashedBox(urwid.Filler(self.here_text, valign='top')),
                ui.DashedBox(urwid.Filler(self.minimap_text, valign='top')),
                ui.DashedBox(urwid.Filler(self.user_text, valign='top'))
            ])
        ])

        self.world_banner = urwid.Text('====welcome 2 tildemush, u are jacked in====')
        self.world_prompt = GamePrompt()
        self.world_view = urwid.Frame(header=self.world_banner,
                body=self.world_body, footer=self.world_prompt)
        self.world_view.focus_position = 'footer'

        self.main_tab = ui.GameTab(self.world_view,
                ui.TabHeader("F1 MAIN", position='first',
                    selected=True))

        # witch view stuff
        self.witch_view = urwid.Filler(urwid.Text("witch editor in progress", align='center'), valign='middle')
        self.witch_tab = ui.GameTab(self.witch_view,
                ui.TabHeader("F2 WITCH"))

        # worldmap view stuff
        self.worldmap_view = urwid.Filler(urwid.Text("worldmap coming soon", align='center'), valign='middle')
        self.worldmap_tab = ui.GameTab(self.worldmap_view,
                ui.TabHeader("F3 WORLDMAP"))

        # settings view stuff
        self.settings_view = urwid.Filler(urwid.Text("settings menu under construction", align='center'), valign='middle')
        self.settings_tab = ui.GameTab(self.settings_view,
                ui.TabHeader("F4 SETTINGS"))

        # quit placeholder
        self.quit_view = self.world_view
        self.quit_tab = ui.GameTab(self.quit_view,
                ui.TabHeader("F9 QUIT", position='last'))

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
        self.prompt = self.world_prompt
        self.main = self.main_tab
        self.statusbar = urwid.Text("connection okay!", align='right')
        self.client_state.set_on_recv(self.on_server_message)
        super().__init__(header=self.header, body=self.main, footer=self.statusbar)
        self.focus_prompt()

    async def on_server_message(self, server_msg):
        if server_msg == 'COMMAND OK':
            pass
        elif server_msg.startswith('here'):
            # TODO: this is kind of filler for now for updating the here
            # panel; consider better data format
            text = ' '.join(server_msg.split(' ')[1:])
            self.here_text.contents.clear()
            self.here_text.contents.append(
                (urwid.Text(text), self.here_text.options()))
        elif server_msg.startswith('info'):
            text = ' '.join(server_msg.split(' ')[1:])
            self.user_text.contents.clear()
            self.user_text.contents.append(
                (urwid.Text(text), self.user_text.options()))
        else:
            new_line = urwid.Text(server_msg)
            self.game_walker.append(new_line)
            self.game_walker.set_focus(len(self.game_walker)-1)

        self.focus_prompt()

    def focus_prompt(self):
        self.focus_position = 'body'
        self.world_view.focus_position = 'footer'

    def keypress(self, size, key):
        if key == 'enter':
            self.handle_game_input(self.prompt.get_edit_text())
        else:
            self.prompt.keypress((size[0],), key)
            self.handle_keypress(key)

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

    def handle_keypress(self, key):
        # debugging output
        self.footer = urwid.Text(key)

        if key == 'f9':
            # TODO: this isn't getting caught by the server for some reason
            asyncio.ensure_future(self.client_state.send('COMMAND QUIT'), loop=self.loop)
            quit_client('')
        elif key in self.tabs.keys():
            # tab switcher
            self.body.unfocus()
            self.body = self.tabs.get(key)
            self.body.focus()
            self.refresh_tabs()

    def refresh_tabs(self):
        self.tab_headers.contents.clear()
        headers = []
        for tab in sorted(self.tabs.keys()):
            headers.append(self.tabs.get(tab).tab_header)

        self.tab_headers = urwid.Columns(headers)
        self.header = self.tab_headers

    def here_info(self):
        room_name = self.room.get("name")
        info = "[{}]".format(room_name)

        return info
    
    def user_info(self):
        info = '<a {desc} named {name}>'.format(
                desc=self.user.get("description"),
                name=self.user.get("name")
                )

        return info
