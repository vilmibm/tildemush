import pytest
import tmclient
import urwid

class TestColorPartsRe():

    COLOR_PARTS_RE = tmclient.ui.COLOR_PARTS_RE
    color_code = "{red}"

    def test_color_code_is_parsed(self):
        parts = self.COLOR_PARTS_RE.findall(self.color_code)
        assert parts[0][1] == self.color_code

    def test_text_is_parsed(self):
        text = "The stream flowed toward the rocks."
        parts = self.COLOR_PARTS_RE.findall(text)
        for part in parts: assert part[1] == ''

    def test_text_and_color_code_are_parsed(self):
        text = "I sent my wishes %s through the fold." % self.color_code
        parts = self.COLOR_PARTS_RE.findall(text)
        for part in parts:
            if part[0] == '':
               assert part[1] == self.color_code

class TestColorText():
    
    ColorText = tmclient.ui.ColorText
    multicolored_text = "I heard the {blue}wind{/} blow through the {green}trees{/}."

    def test_message_is_parsed(self):
        message = self.ColorText(self.multicolored_text) 
        assert ("I heard the wind blow through the trees." in str(message))

        
    def test_message_has_multiple_colors(self):
        widget = self.ColorText(self.multicolored_text)
        attributes = widget.attrib
        assert [color for color in attributes if "blue" and "green" in color] 
