import asyncio
import copy
import json
import os

import urwid
import websockets

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



class Screen(urwid.WidgetPlaceholder):
    """
    Base interface screen with utilities for stacking boxes.
    Override Screen.input to handle keypresses.
    Screen.exit is a callback for when you want to communicate what the screen did
    """
    max_box_levels = 4

    def __init__(self, base, exit=lambda _:True):
        super().__init__(base)
        self.box_level = 0
        self.base = base
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



palettes = [
    ('reversed', 'standout', ''),
    ('basic', 'white', 'black'),
    ('background', 'dark magenta', 'black'),
    ('error', 'light red', 'black')]

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