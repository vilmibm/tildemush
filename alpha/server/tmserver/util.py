import re

ARG_RE_RAW = '(\'[^\']+?\'|"[^"]+?"|[^"\' ]+)'
ARG_RE = re.compile(ARG_RE_RAW)
COLLAPSE_WHITESPACE_RE = re.compile(r'\s+')
QUOTED_RE = re.compile(r'^["\'](.*)["\']$')
STRIP_COLOR_RE = re.compile(r'{[^}]+}')
WHITESPACE_RE = re.compile(r'^\s*$')

def strip_color_codes(string):
    """returns string with {color} {codes} {/} removed"""
    return collapse_whitespace(STRIP_COLOR_RE.sub('', string))

def collapse_whitespace(string):
    return COLLAPSE_WHITESPACE_RE.sub(' ', string).rstrip().lstrip()

def is_whitespace(string):
    return bool(WHITESPACE_RE.fullmatch(string))

def clean_str(string):
    """Given an argument found via split_args, this function:
       - unquotes the string if needed
       - collapses whitespace"""
    out = None
    match = QUOTED_RE.fullmatch(string)

    if match:
        out = match.groups()[0]
    else:
        out = string

    return collapse_whitespace(out)

def split_args(arg_str):
    """Given a string like 'foo bar baz' or '"foo bar" baz quux', returns a
    list of all the quote-delimited or space delimited strings."""
    return [clean_str(s)
            for s
            in ARG_RE.split(arg_str)
            if not (is_whitespace(s) or s in ('"', "'"))]
