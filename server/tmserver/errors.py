class ClientException(Exception): pass
class WitchException(Exception): pass
class UserValidationError(Exception):
    code = 8