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
    ('dark red', 'dark red', ''),
    ('dark green', 'dark green', ''),
    ('brown', 'brown', ''),
    ('dark blue', 'dark blue', ''),
    ('dark magenta', 'dark magenta', ''),
    ('dark cyan', 'dark cyan', ''),
    ('light gray', 'light gray', ''),
    ('dark gray', 'dark gray', ''),
    ('light red', 'light red', ''),
    ('light green', 'light green', ''),
    ('yellow', 'yellow', ''),
    ('light blue', 'light blue', ''),
    ('light magenta', 'light magenta', ''),
    ('light cyan', 'light cyan', ''),
    ('white', 'white', ''),
    ('black', 'black', 'white'),
    ('/', 'white', ''),
    ('reset', 'white', '')]

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
                res.append((theme, text))
                theme = token[1][1:-1]
                text = ''
            elif token[0] == "\{":
                text += "{"
            else:
                text += token[0]
        res.append((theme, text))
        super().__init__(res, align, wrap, layout)


class ExternalEditor(urwid.Terminal):
    def __init__(self, path, loop, callback):
        self.terminated = False
        self.path = path
        self.callback = callback
        command = ["bash", "-c", "{} {}; echo Press any key to kill this window...".format(
            os.environ["EDITOR"], self.path)]
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
