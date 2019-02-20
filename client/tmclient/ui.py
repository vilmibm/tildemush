import asyncio
import copy
import json
import os
import re

import urwid
import websockets

COLOR_PARTS_RE = re.compile('(\\\{|[^\{])|(\{[^\}]+\})')

palettes = [
    ('reversed', 'standout', ''),
    ('basic', 'white', 'black'),
    ('background', 'dark magenta', 'black'),
    ('error', 'light red', 'black'),

    # standard colors - only using foreground colors, eventually
    # we could probably do permutations of fg/bg combinations
    # the names come from http://urwid.org/manual/displayattributes.html
    ('red', 'light red', ''),
    ('green', 'light green', ''),
    ('blue', 'light blue', ''),
    ('magenta', 'light magenta', ''),
    ('cyan', 'light cyan', ''),
    ('gray', 'light gray', ''),
    ('grey', 'light gray', ''),
    ('dark red', 'dark red', ''),
    ('dark green', 'dark green', ''),
    ('brown', 'brown', ''),
    ('dark blue', 'dark blue', ''),
    ('dark magenta', 'dark magenta', ''),
    ('dark cyan', 'dark cyan', ''),
    ('light gray', 'light gray', ''),
    ('light grey', 'light gray', ''),
    ('dark gray', 'dark gray', ''),
    ('dark grey', 'dark gray', ''),
    ('light red', 'light red', ''),
    ('light green', 'light green', ''),
    ('yellow', 'yellow', ''),
    ('light blue', 'light blue', ''),
    ('light magenta', 'light magenta', ''),
    ('light cyan', 'light cyan', ''),
    ('white', 'white', ''),
    ('black', 'black', 'white'),
    ('/', 'default', ''),
    ('reset', 'default', '')]

KEY_ESCAPE_MAP = {
    key: urwid.vterm.ESC + sequence
      for sequence, key in urwid.escape.input_sequences
      if len(key) > 1
}


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
    button = urwid.Button(" "+caption)
    urwid.connect_signal(button, 'click', callback)
    return urwid.AttrMap(button, None, focus_map='reversed')

def sub_menu(this, caption, choices):
    contents = menu(caption, choices)
    def open_menu(button):
        return this.open_box(contents)
    return menu_button(caption+'...', open_menu)

def menu(title, choices):
    if type(title) is str:
        title = urwid.Text(title)
    body = [title, urwid.Divider()]
    body.extend(choices)
    return urwid.ListBox(urwid.SimpleFocusListWalker(body))

def solidfill(s, theme='basic'):
    return urwid.AttrMap(urwid.SolidFill(s), theme)


class DashedBox(urwid.LineBox):
    def __init__(self, box_item):
        super().__init__(box_item,
                tlcorner='┌', tline='╌', lline='╎', trcorner='┐', blcorner='└',
                rline='╎', bline='╌', brcorner='┘'
                )

class SpookyBox(urwid.LineBox):
    def __init__(self, box_item):
        super().__init__(box_item,
                tline='~', bline='~', lline='┆', rline='┆', tlcorner='o',
                trcorner='o', blcorner='o', brcorner='o')

class TabHeader(urwid.LineBox):
    """
    Stylizations for tab headers. Position can be 'first', 'last', or none for
    default/medial tabs. Selected tab displays with no bottom, so it opens into
    the tab contents.
    """

    def __init__(self, label, position="", selected=False):

        tl = '╭'
        tr = '╮'

        self.label = label
        self.contents = urwid.Text(self.label, align='center')
        self.position = position

        if position == 'first':
            if selected:
                bl = '║'
                br = '╙'
            else:
                bl = '├'
                br = '┴'
        elif position == 'last':
            if selected:
                bl = '╜'
                bl = '║'
            else:
                bl = '┴'
                br = '┤'
        else:
            if selected:
                bl = '╜'
                br = '╙'
            else:
                bl = '┴'
                br = '┴'

        if selected:
            b = ' '
            r = '║'
            l = '║'
        else:
            b = '─'
            r = '│'
            l = '│'

        super().__init__(self.contents, tlcorner=tl, trcorner=tr,
                blcorner=bl, brcorner=br, bline=b,
                lline =l, rline=r)


class Screen(urwid.WidgetPlaceholder):
    """
    Base interface screen with utilities for stacking boxes.
    Override Screen.input to handle keypresses.
    Screen.exit is a callback for when you want to communicate what the screen did
    """
    max_box_levels = 4

    def __init__(self, base, client=None, exit=lambda _:True):
        super().__init__(base)
        self.box_level = 0
        self.base = base
        self.client = client
        self.exit = exit

    def input(self, key):
        return False

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

    def close_box(self):
        if self.box_level > 0:
            self.original_widget = self.original_widget[0]
            self.box_level -= 1

    def message(self, s, palette='basic'):
        self.open_box(menu(urwid.Text((palette, s)), 
            [menu_button('ESC', lambda _:self.close_box())]))

    def keypress(self, size, key):
        if self.input(key):
            pass
        elif key == 'esc' and self.box_level > 1:
            self.close_box()
        else:
            return super(Screen, self).keypress(size, key)

class GamePrompt(urwid.Edit):
    def __init__(self):
        self.history = [""]
        self.input_index = 0
        super().__init__(caption='> ', multiline=True)

    def add_line(self, line):
        blank = self.history.pop()
        self.history.append(line)
        self.history.append(blank)
        self.input_index += 1

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
        self.rlwrap_set(max(0, self.input_index - 1))

    def rlwrap_down(self):
        self.rlwrap_set(min(len(self.history) - 1, self.input_index + 1))

    def rlwrap_set(self, index):
        self.input_index = index
        self.edit_text = self.history[self.input_index]
        self.rlwrap_end()

    def rlwrap_start(self):
        self.set_edit_pos(0)

    def rlwrap_end(self):
        self.set_edit_pos(len(self.edit_text))

    def rlwrap_delete_backwards(self):
        self.edit_text = self.edit_text[self.edit_pos:]
        self.rlwrap_start()

    def rlwrap_delete_forwards(self):
        self.edit_text = self.edit_text[0:self.edit_pos]
        self.rlwrap_end()

class GameTab(urwid.WidgetPlaceholder):
    """
    Base interface for a tab within the main game area.
    """

    def __init__(self, widget, tab_header, prompt):
        self.main = urwid.LineBox(widget, tlcorner='│', trcorner='│', tline='')
        self.tab_header = tab_header
        self.prompt = prompt
        self.in_focus = False
        super().__init__(self.main)

    def focus(self):
        self.in_focus = True
        self.tab_header = TabHeader(self.tab_header.label, self.tab_header.position, True)

    def unfocus(self):
        self.in_focus = False
        self.tab_header = TabHeader(self.tab_header.label, self.tab_header.position, False)

    def mount(self, widget):
        self.original_widget = urwid.LineBox(widget, tlcorner='│', trcorner='│', tline='')
        self.prompt = widget



class ColorText(urwid.Text):
    """
    Turns a string into a text widget with colorized sections.
    Strings use a format of "{light red}foo {light blue}bar{/}"
    """

    def __init__(self, s, align='left', wrap='space', layout=None):
        parts = COLOR_PARTS_RE.findall(s)
        res = []
        text = ""
        theme = ""
        for token in parts:
            if token[1] != '':
                if text != '':
                    res.append((theme, text))
                theme = token[1][1:-1]
                text = ''
            elif token[0] == "\{":
                text += "{"
            else:
                text += token[0]
        res.append((theme, text))
        super().__init__(res, align, wrap, layout)

class WitchView(GameTab):

    def __init__(self, object_data, scope, config):
        self.scope = scope
        self.config = config
        self.info = {
                "edit area": "NO OBJECT LOADED! /edit an object in the game view to work on it here.",
                "data": "Current Object: <None>",
                "perms": "Permissions: <unknown>",
                "status": "WITCH STATUS: <unknown>"
                }

        self.editor_filler = urwid.Pile([ColorText(self.info.get("edit area"),
            align='center'), self.scope_list(scope)])
        self.editor = urwid.Filler(self.editor_filler)
        self.editor_box = SpookyBox(self.editor)
        self.status = urwid.Pile([ColorText(self.info.get("status"))])
        self.data = urwid.Filler(ColorText(self.info.get("data")))
        self.perms = urwid.Filler(ColorText(self.info.get("perms")))
        self.body = urwid.Pile([
                urwid.Columns([
                    self.data,
                    self.perms
                ]),
                self.editor_box
            ])
        self.prompt = self.editor
        self.view = urwid.Frame(body=self.body, footer=self.status)
        self.view.focus_position = 'body'
        super().__init__(self.view, TabHeader("F2 WITCH"), self.prompt)

    def refresh(self, object_data, scope):
        self.editor_filler.contents.pop()
        self.editor_filler.contents.append((
            self.scope_list(scope), self.editor_filler.options()
            ))
        self.status.contents.pop()
        self.status.contents.append((self.update_object(object_data),
            self.status.options()))

    def scope_list(self, scope):
        if len(scope) == 0:
            scope = ["none"]

        return ColorText("available objects: {}".format(", ".join(sorted(scope))))

    def update_object(self, object_data):
        revision = object_data.get("current_rev", "<??>")
        return ColorText("ver. {}".format(revision))

class WorldmapView(GameTab):
    def __init__(self, config):
        self.prompt = urwid.Edit()
        self.config = config
        # TODO be able to render scrollable text; what urwid thing to use?
        self.rendered_map = 'something should show here...'
        self.view = urwid.Filler(ColorText(self.rendered_map, align='center'), valign='middle')
        super().__init__(self.view, TabHeader("F3 WORLDMAP"), self.prompt)

    def update_map(self, rendered_map):
        self.rendered_map = rendered_map
        self.view.original_widget = ColorText(self.rendered_map, align='center')


class SettingsView(GameTab):
    def __init__(self, config):
        self.config = config
        self.prompt = urwid.Edit()
        self.view = urwid.Filler(ColorText("settings menu under construction", align='center'), valign='middle')
        super().__init__(self.view, TabHeader("F4 SETTINGS"), self.prompt)

class GameView(GameTab):

    def __init__(self, state, config):
        self.config = config
        self.game_walker = urwid.SimpleFocusListWalker([
            ColorText('{yellow}you have reconstituted into tildemush'),
            ColorText("")
            ])
        self.game_area = urwid.ListBox(self.game_walker)
        self.here_text = urwid.Pile(self.here_info(state))
        self.user_text = urwid.Pile(self.user_info(state))
        self.minimap_grid = urwid.Pile(self.generate_minimap(state))
        self.panel_layout = config.get("panel_layout",
                ["here", "minimap", "user"])

        self.body = urwid.Columns([self.game_area])
        if len(self.panel_layout) > 0:
            self.body.contents.append((urwid.Pile(
                self.generate_panel_display(self.panel_layout)),
                self.body.options()))
        self.banner = ColorText('====welcome 2 tildemush, u are jacked in====')
        self.prompt = GamePrompt()
        self.view = urwid.Frame(header=self.banner,
                body=self.body, footer=self.prompt)
        self.view.focus_position = 'footer'

        super().__init__(self.view,
                TabHeader("F1 MAIN", position='first',
                    selected=True), self.prompt)

    def add_message(self, msg):
        spacer = self.game_walker.pop()
        self.game_walker.append(ColorText(msg))
        self.game_walker.append(spacer)
        self.game_walker.set_focus(len(self.game_walker)-1)

    def refresh(self, state):

        self.here_text.contents.clear()
        self.user_text.contents.clear()
        self.minimap_grid.contents.clear()

        # TODO: this is kind of hardcoded for the current three-widget
        # here_info(), two-widget user_info(), three-widget generate_minimap()

        self.here_text.contents.extend(list(
            zip(self.here_info(state),
                [self.here_text.options(),
                    self.here_text.options(),
                    self.here_text.options()]
                )
            ))

        self.user_text.contents.extend(list(
            zip(self.user_info(state),
                [self.user_text.options(),
                    self.user_text.options()]
                )
            ))

        self.minimap_grid.contents.extend(list(
            zip(self.generate_minimap(state),
                [self.minimap_grid.options(),
                    self.minimap_grid.options(),
                    self.minimap_grid.options()]
                )
            ))

    def here_info(self, state):
        room = state.get("room", {})
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

    def user_info(self, state):
        user = state.get("user", {})
        inventory = []

        for item in state.get("inventory", []):
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

    def generate_minimap(self, state):
        """Generates a minimap for the cardinal exits of the current room."""
        room = state.get("room", {})
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
            node = urwid.LineBox(ColorText(target.get("room_name", "(somewhere)"), align='center'))
            map_nodes.update({direction: node})

        map_grid = [
                urwid.Columns([
                    map_nodes.get("above"),
                    map_nodes.get("north"),
                    urwid.Text(" ")
                    ]),
                urwid.Columns([
                    map_nodes.get("west"),
                    urwid.LineBox(ColorText(room.get("name", "somewhere"), align='center')),
                    map_nodes.get("east")
                    ]),
                urwid.Columns([
                    urwid.Text(" "),
                    map_nodes.get("south"),
                    map_nodes.get("below")
                    ])
                ]

        return map_grid

    def generate_panel_display(self, layout):
        panels = {
                "here": DashedBox(urwid.Filler(self.here_text, valign='top')),
                "minimap": DashedBox(urwid.Filler(self.minimap_grid, valign='middle')),
                "user": DashedBox(urwid.Filler(self.user_text, valign='top'))
                }

        panel_display = []
        for panel in layout:
            panel_display.append(panels.get(panel))
        return panel_display

class ExternalEditor(urwid.Terminal):
    def __init__(self, path, loop, callback):
        self.terminated = False
        self.path = path
        self.callback = callback
        # TODO: hardcoded nano as default editor; make this more flexible in
        # the future
        editor = os.environ.get("EDITOR", "/bin/nano")
        command = ["bash", "-c", "{} {}; echo Press any key to kill this window...".format(
            editor, self.path)]
        super(ExternalEditor, self).__init__(command, os.environ, loop, "ctrl z")
        urwid.connect_signal(self, "closed", self.exterminate)

    def exterminate(self, *_):
        if self.callback:
            self.callback(self.path)

    def keypress(self, size, key):
        """
        The majority of the things the parent keypress method will do is
        either erroneous or disruptive to my own usage. I've plucked out
        the necessary bits and, most importantly, have changed from
        ASCII encoding to utf8 when writing to the child process.
        """

        #print("("+key+")")
        if self.terminated:
            return

        self.term.scroll_buffer(reset=True)
        keyl = key.lower()

        if keyl == "ctrl z":
            return os.killpg(os.getpgid(os.getpid()), 19)

        single_char = len(key) == 6
        if key.startswith("ctrl ") and single_char:
            if key[-1].islower():
                key = chr(ord(key[-1]) - ord("a") + 1)
            else:
                key = chr(ord(key[-1]) - ord("A") + 1)

        elif key.startswith("meta ") and single_char:
            key = urwid.vterm.ESC + key[-1]

        elif key in urwid.vterm.KEY_TRANSLATIONS:
            key = urwid.vterm.KEY_TRANSLATIONS[key]

        elif key in KEY_ESCAPE_MAP:
            key = KEY_ESCAPE_MAP[key]


        if self.term_modes.lfnl and key == "\x0d":
            key += "\x0a"

        os.write(self.master, key.encode("utf8"))


class UI:
    def __init__(self, loop):
        base = urwid.SolidFill("")
        self.loop = urwid.MainLoop(
            base,
            event_loop=urwid.AsyncioEventLoop(loop=loop),
            palette=palettes)
        self.base = base

    @property
    def base(self):
        return self.__base

    @base.setter
    def base(self, base):
        self.__base = base
        self.loop.widget = base
