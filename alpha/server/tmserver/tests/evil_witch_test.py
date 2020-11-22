from unittest.mock import MagicMock
from ..errors import WitchError
from ..models import GameObject, Script, ScriptRevision, UserAccount, Permission
from ..world import GameWorld
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
        (incantation by someone
           (has {"foo" "bar"})
           (provides "lol"
              (import [tmserver.models [UserAccount]])
              (for [ua (.select UserAccount)]
                (says ua.username))))"""
        game_obj = self.create_obj_with_code(code)

        with self.assertRaisesRegex(NotImplementedError, 'ImportFrom') as cm:
            game_obj.init_scripting(use_db_data=False)
            game_obj.handle_action(GameWorld, game_obj, 'lol', '')

    def test_prevents_db_access_via_model(self):
        code = """
        (incantation by someone
           (has {"foo" "bar"})
           (provides "lol"
              (for [ua (this.author.select)]
                (says ua.username))))"""
        game_obj = self.create_obj_with_code(code)

        with self.assertRaisesRegex(AttributeError, 'author') as cm:
            game_obj.init_scripting(use_db_data=False)
            game_obj.handle_action(GameWorld, game_obj, 'lol', '')

    def test_prevents_malicious_introspection(self):
        code = """
        (incantation by someone
          (has {"foo" "bar"})
          (provides "lol"
            ((get (.__subclasses__ (get print.__class__.__bases__ 0)) 323) "bash")))
        """
        game_obj = self.create_obj_with_code(code)

        with self.assertRaisesRegex(AttributeError, '__class__') as cm:
            game_obj.init_scripting()
            game_obj.handle_action(GameWorld, game_obj, 'lol', '')

    def test_prevents_opening_files(self):
        code = """
        (incantation by someone
          (has {"foo" "bar"})
          (provides "lol"
            (says (.readlines (open "/tmp/foo")))))
        """
        game_obj = self.create_obj_with_code(code)

        with self.assertRaisesRegex(NotImplementedError, 'witch_open') as cm:
            game_obj.init_scripting()
            game_obj.handle_action(GameWorld, game_obj, 'lol', '')
