class RevisionError(Exception):
    def __init__(self, *args, **kwargs):
        payload = kwargs.pop('payload')
        super().__init__(*args, **kwargs)
        self.payload = payload

class ClientError(Exception):
    """This exception represents an exception that should make it all the way
    back to the client for handling there. It's not necessarily one that we
    want a user to know about and it usually represents something broken about
    the game's world state or a bug. It should be considered very bad to let
    one of these actually get to the client."""
    pass

class UserError(Exception):
    """This exception implies that a user did something sort of wrong, like
    trying to go a direction there is no exit defined for. Ideally this is
    caught at the server level and just results in a user hearing some red text
    about what they tried to do."""

class ClientQuit(Exception): pass
class WitchError(Exception): pass
class UserValidationError(Exception):
    code = 8
