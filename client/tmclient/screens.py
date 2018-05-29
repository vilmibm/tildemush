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

class DashedBox(urwid.LineBox):
    def __init__(self, box_item):
        super().__init__(box_item,
                tlcorner='┌', tline='╌', lline='╎', trcorner='┐', blcorner='└',
                rline='╎', bline='╌', brcorner='┘'
                )

class TabHeader(urwid.LineBox):
    def __init__(self, contents, position=""):
        if position == 'first':
            super().__init__(contents, tlcorner='╭', trcorner='╮',
                    bline=' ', blcorner='│', brcorner='└')
        elif position == 'last':
            super().__init__(contents, tlcorner='╭', trcorner='╮',
                    blcorner='┴', brcorner='┤')
        else:
            super().__init__(contents, tlcorner='╭', trcorner='╮',
                    blcorner='┴', brcorner='┴')

class GameMain(urwid.Frame):
    def __init__(self, client_state, loop):
        self.client_state = client_state
        self.loop = loop
        # TODO: get room and user info passed in on init?
        self.room = {}
        self.user = {}
        self.banner = urwid.Text('====welcome 2 tildemush, u are jacked in====')
        self.tabs = [
                    TabHeader(urwid.Text("F1 MAIN"), position='first'),
                    TabHeader(urwid.Text("F2 WITCH")),
                    TabHeader(urwid.Text("F3 WORLDMAP")),
                    TabHeader(urwid.Text("F4 SETTINGS")),
                    TabHeader(urwid.Text("F12 QUIT"), position='last')
                ]

        self.header = urwid.Columns(self.tabs)

        # game view stuff
        self.game_text = urwid.Pile([
            urwid.Text('you have reconstitued as {desc} in {location}'.format(
                desc=self.user.get("description"),
                location=self.room.get("name")
                ))
            ])
        self.here_text = urwid.Text(self.here_info())
        self.user_text = urwid.Text(self.user_info())
        self.minimap_text = urwid.Text("MAP")
        self.world_body = urwid.LineBox(urwid.Columns([
            urwid.Filler(self.game_text, valign='top'),
            urwid.Pile([
                DashedBox(urwid.Filler(self.here_text, valign='top')),
                DashedBox(urwid.Filler(self.minimap_text, valign='top')),
                DashedBox(urwid.Filler(self.user_text, valign='top'))
            ])
        ]), tlcorner='│', trcorner='│', tline='')

        self.world_prompt = GamePrompt()
        self.world_banner = urwid.Text("WORLD VIEW")

        self.world_view = urwid.Frame(header=self.world_banner,
                body=self.world_body, footer=self.world_prompt)

        # set starting conditions
        self.prompt = GamePrompt()
        self.main = self.world_body
        self.client_state.set_on_recv(self.on_server_message)
        super().__init__(header=self.header, body=self.main, footer=self.prompt)
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
