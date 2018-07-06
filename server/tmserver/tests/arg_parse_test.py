from .tm_test_case import TildemushUnitTestCase
from ..util import split_args


class ArgParseTest(TildemushUnitTestCase):
    def test_single_quotes(self):
        inputs = [
            ("'hi there' how are you", ['hi there', 'how', 'are', 'you']),
            ("hi 'there how' are you", ['hi', 'there how', 'are', 'you']),
            ("hi 'there how' 'are you' today", ['hi', 'there how', 'are you', 'today']),
            ("'hi there' 'how are'", ['hi there', 'how are'])
        ]
        for i in inputs: assert i[1] == split_args(i[0])

    def test_double_quotes(self):
        inputs = [
            ('"hi there" how are you', ['hi there', 'how', 'are', 'you']),
            ('hi "there how" are you', ['hi', 'there how', 'are', 'you']),
            ('hi "there how" "are you" today', ['hi', 'there how', 'are you', 'today']),
            ('"hi there" "how are"', ['hi there', 'how are'])
        ]
        for i in inputs: assert i[1] == split_args(i[0])

    def test_no_quotes(self):
        inputs = [
            ('hi', ['hi']),
            ('hi there', ['hi', 'there']),
            ('hi there how', ['hi', 'there', 'how']),
        ]
        for i in inputs: assert i[1] == split_args(i[0])

    def test_extra_whitespace(self):
        inputs = [
            ('   hi', ['hi']),
            ('   hi    ', ['hi']),
            ('hi    ', ['hi']),
            ('hi    there', ['hi', 'there']),
            ('hi    there      ', ['hi', 'there']),
            ('hi   "there how    " are you', ['hi', 'there how', 'are', 'you'])
        ]
        for i in inputs: assert i[1] == split_args(i[0])

    def test_mix(self):
        i = 'hi "is this vil\'s garbage" \'how are you\' i am fine'
        o = ['hi', "is this vil's garbage", 'how are you', 'i', 'am', 'fine']
        assert o == split_args(i)

    def test_unbalanced_quotes(self):
        inputs = [
            ('"hi there how', ['hi', 'there', 'how']),
            ('hi there how"', ['hi', 'there', 'how']),
            ("'hi there how", ['hi', 'there', 'how']),
            ("hi there how'", ['hi', 'there', 'how']),
        ]
        for i in inputs: assert i[1] == split_args(i[0])
