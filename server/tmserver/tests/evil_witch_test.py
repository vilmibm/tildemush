from unittest.mock import MagicMock
from ..errors import WitchError
from ..models import GameObject, Script, ScriptRevision, UserAccount, Permission
from .tm_test_case import TildemushTestCase

class EvilWitchTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.ua = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')

    def create_obj_with_code(self, code):
        script = Script.create(
            author=self.ua,
            name='something nasty')
        scriptrev = ScriptRevision.create(
            script=script,
            code=code)
        return GameObject.create(
            perms=Permission(),
            author=self.ua,
            shortname='something nasty',
            script_revision=scriptrev)


    def test_prevents_import(self):
        code = """
        (witch "foo"
           (has {"foo" "bar"})
           (hears "lol"
              (import [tmserver.models [UserAccount]])
              (for [ua (.select UserAccount)]
                (says ua.username))))"""
        game_obj = self.create_obj_with_code(code)

        with self.assertRaisesRegex(NotImplementedError, 'ImportFrom') as cm:
            game_obj.init_scripting()
            game_obj.engine.handlers['lol'](MagicMock(), MagicMock(), MagicMock())
