# TODO unit test parse_revision
# TODO unit test handle_revision
# TODO unit test UserSession.handle_revision
# TODO unit test GameWorld.handle_revision
# TODO unit test revision update handling in GameObject.engine()

from .tm_test_case import TildemushTestCase

class GameServerRevisionHandlingTest(TildemushTestCase):

    def test_require_auth(self):
        pass

    def test_malformed_payload(self):
        pass

    def test_missing_keys(self):
        pass

    def test_bad_json(self):
        pass

    def test_chill(self):
        pass

class UserSessionRevisionHandlingTest(TildemushTestCase):
    def test_revision_error(self):
        pass

    def test_chill(self):
        pass

class GameWorldRevisionHandlingTest(TildemushTestCase):
    def test_perm_denied(self):
        pass

    def test_revision_mismatch(self):
        pass

    def test_no_change(self):
        pass

    def test_witch_error(self):
        pass

    def test_chill(self):
        pass

class GameObjectRevisionUpdateTest(TildemushTestCase):
    def test_already_on_latest_rev(self):
        pass

    def test_witch_error(self):
        # TODO the behavior for this is undefined
        pass

    def test_chill(self):
        pass
