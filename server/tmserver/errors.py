class RevisionException(Exception):
    def __init__(self, *args, **kwargs):
        payload = kwargs.pop('payload')
        super().__init__(*args, **kwargs)
        self.payload = payload

class ClientException(Exception): pass
class ClientQuit(Exception): pass
class WitchException(Exception): pass
class UserValidationError(Exception):
    code = 8
