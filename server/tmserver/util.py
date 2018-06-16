import re

STRIP_COLOR_RE = re.compile(r'{[^}]+}')
COLLAPSE_WHITESPACE_RE = re.compile(r'\s+')

def strip_color_codes(string):
    """returns string with {color} {codes} {/} removed"""
    return collapse_whitespace(STRIP_COLOR_RE.sub('', string))

def collapse_whitespace(string):
    return COLLAPSE_WHITESPACE_RE.sub(' ', string).rstrip().lstrip()

