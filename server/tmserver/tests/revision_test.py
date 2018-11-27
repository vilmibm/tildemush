import json
from unittest.mock import Mock, patch

from ..core import GameServer, UserSession
from ..errors import ClientError, RevisionError
from ..models import GameObject, UserAccount, ScriptRevision
from ..world import GameWorld
from .tm_test_case import TildemushTestCase, TildemushUnitTestCase

class GameServerRevisionHandlingTest(TildemushUnitTestCase):
    def setUp(self):
        super().setUp()
        self.sess = Mock()
        self.sess.associated = True
        self.gs = GameServer(GameWorld)

    def test_require_auth(self):
        self.sess.associated = False
        with self.assertRaisesRegex(ClientError, 'not logged in'):
            self.gs.handle_revision(self.sess, 'REVISION {}')

    def test_malformed_payload(self):
        malformed = [
            'REVISONfoo',
            'REVISIONS {}',
        ]
        for bad in malformed:
            with self.assertRaisesRegex(
                    ClientError,
                    'malformed revision'):
                self.gs.handle_revision(self.sess, bad)

    def test_missing_keys(self):
        payload = {
            'shortname': 'hmm',
            'code': '(fart)'}
        with self.assertRaisesRegex(
                ClientError,
                'revision payload missing key'):
            self.gs.handle_revision(self.sess, 'REVISION {}'.format(json.dumps(payload)))

    def test_bad_json(self):
        with self.assertRaisesRegex(
                ClientError,
                'failed to parse'):
            self.gs.handle_revision(self.sess, 'REVISION {"rad":"yeah"')

    # golden path test starting from core is in async_test

class UserSessionRevisionHandlingTest(TildemushUnitTestCase):
    def test_revision_error(self):
        sess = UserSession(Mock(), GameWorld, Mock())
        sess.user_account = Mock()
        payload, error = (None, None)
        with patch('tmserver.GameWorld.handle_revision', side_effect=RevisionError(
                'aw shit',
                payload={'fun': 'times'})):
            payload, error = sess.handle_revision('vilmibm/snoozy', '(ohno)', 3)

        assert payload == {'fun': 'times'}
        assert error == 'aw shit'

    def test_success(self):
        sess = UserSession(Mock(), GameWorld, Mock())
        sess.user_account = Mock()
        payload, error = (None, None)
        with patch('tmserver.GameWorld.handle_revision', return_value={'sweet':'yeah'}):
            payload, error = sess.handle_revision('vilmibm/snoozy', '(awyis)', 3)

        assert payload == {'sweet': 'yeah'}
        assert error == None

class GameWorldRevisionHandlingTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')
        self.someone = UserAccount.create(
            username='someone',
            password='foobarbazquux')
        self.snoozy = GameObject.create_scripted_object(
            self.vil, 'vilmibm/snoozy', 'item', dict(
                name='snoozy',
                description='just a horse'))
        self.book = GameObject.create_scripted_object(
            self.someone, 'someone/book', 'item', dict(
                name='Book',
                description='Electronic Life by Michael Crichton'))

    def test_perm_denied(self):
        cm = None
        with self.assertRaisesRegex(
                RevisionError,
                'Tried to edit illegal') as cm:
            GameWorld.handle_revision(
                self.vil.player_obj,
                'someone/book',
                '(lol)',
                self.book.script_revision.id)

        assert cm.exception.payload == {
            'shortname': 'someone/book',
            'data': {'description': 'Electronic Life by Michael Crichton', 'name':'Book'},
            'permissions': {'carry': 'world',
                            'execute': 'world',
                            'read': 'world',
                            'write': 'owner'},
            'current_rev': self.book.script_revision.id,
            'code': self.book.get_code()}

    def test_revision_mismatch(self):
        cm = None
        with self.assertRaisesRegex(
                RevisionError,
                'Revision mismatch') as cm:
            GameWorld.handle_revision(
                self.vil.player_obj,
                'vilmibm/snoozy',
                '(lol)',
                self.snoozy.script_revision.id - 1)

        assert cm.exception.payload == {
            'shortname': 'vilmibm/snoozy',
            'data': {'description': 'just a horse', 'name':'snoozy'},
            'permissions': {'carry': 'world',
                            'execute': 'world',
                            'read': 'world',
                            'write': 'owner'},
            'current_rev': self.snoozy.script_revision.id,
            'code': self.snoozy.get_code()}

    def test_no_change(self):
        result = GameWorld.handle_revision(
            self.vil.player_obj,
            'vilmibm/snoozy',
            self.snoozy.get_code(),
            self.snoozy.script_revision.id)

        # TODO what to do here? this is failing as expected. how to have a
        # meaningful code equivalency test?

        assert result == {
            'shortname': 'vilmibm/snoozy',
            'data': {'description': 'just a horse', 'name':'snoozy'},
            'permissions': {'carry': 'world',
                            'execute': 'world',
                            'read': 'world',
                            'write': 'owner'},
            'current_rev': self.snoozy.script_revision.id,
            'code': self.snoozy.get_code()}

    def test_witch_error(self):
        bad_code = '(lol)'
        result = GameWorld.handle_revision(
            self.vil.player_obj,
            'vilmibm/snoozy',
            bad_code,
            self.snoozy.script_revision.id)
        latest_rev = self.snoozy.latest_script_rev
        expected = {
            'shortname': 'vilmibm/snoozy',
            'data': {'description': 'just a horse', 'name':'snoozy'},
            'permissions': {'carry': 'world',
                            'execute': 'world',
                            'read': 'world',
                            'write': 'owner'},
            'current_rev': latest_rev.id,
            'code': bad_code,
            'errors': [";_; There is a problem with your witch script: name 'lol' is not defined"]}

        assert latest_rev.code == bad_code
        assert self.snoozy.script_revision.code != latest_rev.code

        assert expected == result

    def test_success(self):
        new_code = """
        (incantation "snoozy"
          (has {"name" "snoozy"  "description" "just a horse"})
          (provides "pet"
             (says "neigh")))
        """.rstrip().lstrip()
        result = GameWorld.handle_revision(
            self.vil.player_obj,
            'vilmibm/snoozy',
            new_code,
            self.snoozy.script_revision.id)
        latest_rev = self.snoozy.latest_script_rev
        expected = {
            'shortname': 'vilmibm/snoozy',
            'data': {'description': 'just a horse', 'name':'snoozy'},
            'permissions': {'carry': 'world',
                            'execute': 'world',
                            'read': 'world',
                            'write': 'owner'},
            'current_rev': latest_rev.id,
            'code': new_code,
            'errors': []}

        assert latest_rev.code == new_code
        assert self.snoozy.script_revision.code != latest_rev.code

        assert expected == result


class GameObjectRevisionUpdateTest(TildemushTestCase):
    def setUp(self):
        super().setUp()
        self.vil = UserAccount.create(
            username='vilmibm',
            password='foobarbazquux')
        self.snoozy = GameObject.create_scripted_object(
            self.vil, 'vilmibm/snoozy', 'item', dict(
                name='snoozy',
                description='just a horse'))

    def test_already_on_latest_rev(self):
        assert self.snoozy._engine is not None
        with patch('tmserver.scripting.ScriptedObjectMixin.init_scripting') as m:
            e = self.snoozy.engine
        assert e is not None
        assert not m.called

    def test_witch_error(self):
        # I haven't really thought through the behavior here. currently, a
        # witch exception means that the game object just stays with its
        # current _engine and current revision.
        assert self.snoozy._engine
        new_code = "(lol)".rstrip().lstrip()
        current_rev = self.snoozy.script_revision
        GameWorld.handle_revision(
            self.vil.player_obj,
            'vilmibm/snoozy',
            new_code,
            self.snoozy.script_revision.id)
        self.snoozy.engine
        assert self.snoozy.script_revision.id == current_rev.id

    def test_success(self):
        assert self.snoozy._engine
        new_code = """
        (incantation "snoozy"
          (has {"name" "snoozy"
                "description" "just a horse"})
          (provides "pet"
             (says "neigh")))
        """.rstrip().lstrip()
        current_rev = self.snoozy.script_revision
        GameWorld.handle_revision(
            self.vil.player_obj,
            'vilmibm/snoozy',
            new_code,
            self.snoozy.script_revision.id)
        e = self.snoozy.engine
        assert self.snoozy.script_revision.id != current_rev.id
        assert 'pet' in e.provides
