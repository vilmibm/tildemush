from fnmatch import fnmatch
import io
import re

import asteval
import hy
from hy.compiler import hy_compile

from .config import get_db
from .errors import ClientError, WitchError
from .util import split_args

WITCH_HEADER = '(require [tmserver.witch_header [*]])'
ERROR_CLEANUP_RE = re.compile(r' in expr=.*$')

# Note an awful thing here; since we call .format on the script templates, we
# have to escape the WITCH macro's {}. {{}} is not the Hy that we want, but we
# need it in the templates.
# TODO consider using shortname instead of name for the string passed to (witch)
SCRIPT_TEMPLATES = {
    'item': '''
    (incantation by {author}
      (has {{"name" "{name}"
            "description" "{description}"}}))
    ''',
    'player': '''
    (incantation by {author}
      (has {{"name" "{name}"
            "description" "{description}"}}))
    ''',
    'room': '''
    (incantation by {author}
      (has {{"name" "{name}"
            "description" "{description}"}}))
    ''',
    'exit': '''
    (incantation by {author}
      (has {{"name" "{name}"
            "description" "{description}"}})
      (provides "go" (move-sender arg))),
    ''',
    'portkey': '''
    (incantation by {author}
      (has {{"name" "{name}"
            "description" "{description}"
            "target" "{target_room_name}"}})
      (provides "touch"
        (teleport-sender (get-data "target"))))
    '''}


def wildcard_match(pattern, string):
    """This is pretty silly, but it's a small wrapper around fnmatch for
    matching wildcarded strings (as opposed to regexes). For now just using
    fnmatch seems fine even if we aren't actually matching filenames. lulz."""
    return fnmatch(string, pattern)

class ProxyGameObject:
    def __init__(self, game_object):
        self.id = game_object.id
        self.shortname = game_object.shortname

    def __eq__(self, other):
        return self.id == other.id

class WitchInterpreter:
    def __init__(self, receiver_model):
        script_engine = ScriptEngine(receiver_model)
        # TODO we are expanding to different kinds of handlers:
        # - "hear" handlers, actions taken when an object just hears someone say some wildcarded string.
        # - transitive "provides", actions that occur when people invoke a
        #   command that matches some pattern where the pattern includes
        #   "$this"
        # - intransitive "provides", actions that occur when someone just invokes an untargeted command.

        def add_hears_handler(hear_string, callback):
            nonlocal script_engine
            # TODO extend support for this into GameWorld
            script_engine.add_hears_handler(hear_string, callback)

        def add_provides_handler(action, callback):
            nonlocal script_engine
            script_engine.add_provides_handler(action, callback)

        def set_data(key, value):
            nonlocal receiver_model
            receiver_model.set_data(key, value)

        def get_data(key):
            nonlocal receiver_model
            return receiver_model.get_data(key)

        def says(message):
            nonlocal receiver_model
            receiver_model.say(message)

        def does(message):
            nonlocal receiver_model
            receiver_model.emote(message)

        def add_docstring(docstring):
            pass

        def tell_sender(sender_obj, action, args):
            nonlocal receiver_model
            sender_obj = receiver_model.get_by_id(sender_obj.id)
            receiver_model.tell_sender(sender_obj, action, args)

        def move_sender(sender_obj, target_room_name):
            nonlocal receiver_model
            sender_obj = receiver_model.get_by_id(sender_obj.id)
            receiver_model.move_sender(sender_obj, target_room_name)

        def teleport_sender(sender_obj, target_room_name):
            """Given a ProxyGameObject, find the actual gameobject and move it."""
            nonlocal receiver_model
            sender_obj = receiver_model.get_by_id(sender_obj.id)
            receiver_model.teleport_sender(sender_obj, target_room_name)

        def ensure_obj_data(data):
            nonlocal receiver_model
            receiver_model._ensure_data(data)

        def set_permissions(perm_dict):
            nonlocal receiver_model
            receiver_model.set_perms(**perm_dict)

        def witch_open(*args, **kwargs):
            raise NotImplementedError("No file access in WITCH")

        self.script_engine = script_engine
        self.interpreter = asteval.Interpreter(
            use_numpy=False,
            max_time=100000.0,  # there's a bug with this and setting it arbitrarily high avoids it
            usersyms=dict(
                open=witch_open,
                split_args=split_args,
                add_provides_handler=add_provides_handler,
                add_hears_handler=add_hears_handler,
                set_data=set_data,
                get_data=get_data,
                says=says,
                does=does,
                set_permissions=set_permissions,
                add_docstring=add_docstring,
                witch_tell_sender=tell_sender,
                witch_move_sender=move_sender,
                witch_teleport_sender=teleport_sender,
                ensure_obj_data=ensure_obj_data))

    def evaluate_ast(self, witch_ast):
        self.interpreter(witch_ast)
        if self.interpreter.error_msg:
            error_msg = self.interpreter.error_msg
            if 'in expr' in error_msg:
                error_msg = ERROR_CLEANUP_RE.sub('', error_msg)
            raise WitchError(error_msg)


class ScriptEngine:
    CONTAIN_TYPES = {'acquired', 'entered', 'lost', 'freed'}
    def __init__(self, receiver_model):
        self.receiver_model = receiver_model
        self.hears = {}
        self.provides = {'debug': self._debug_handler,
                         'contain': self._contain_handler,
                         'say': self._say_handler,
                         'emote': self._emote_handler,
                         'announce': self._announce_handler,
                         'whisper': self._whisper_handler}

    @staticmethod
    def noop(*args, **kwargs):
        pass

    def _ensure_game_world(self, game_world):
        if not hasattr(self, 'game_world'):
            self.game_world = game_world

    def _debug_handler(self, receiver, sender, _, action_args):
        receiver = self.receiver_model.get_by_id(receiver.id)
        sender = self.receiver_model.get_by_id(sender.id)
        return '{} <- {} with {}'.format(receiver, sender, action_args)

    def _contain_handler(self, receiver, sender, _, action_args):
        receiver = self.receiver_model.get_by_id(receiver.id)
        contain_type = action_args
        if contain_type not in self.CONTAIN_TYPES:
            raise ClientError('Bad container relation: {}'.format(contain_type))
        if receiver.user_account:
            self.game_world.send_client_update(receiver.user_account)
            # TODO we actually want the client to show messages about these
            # events, i think. we can implement that once we actually implement
            # movement and inventory commands. until then we just care that the
            # client_state payload is sent.

    def _announce_handler(self, receiver, sender, _, action_args):
        receiver = self.receiver_model.get_by_id(receiver.id)
        sender = self.receiver_model.get_by_id(sender.id)
        if receiver.user_account:
            msg = "The very air around you seems to shake as {}'s booming voice says {}".format(
                sender.name, action_args)
            self.game_world.user_hears(receiver, sender, msg)

    def _emote_handler(self, receiver, sender, _, action_args):
        receiver = self.receiver_model.get_by_id(receiver.id)
        sender = self.receiver_model.get_by_id(sender.id)
        if receiver.user_account:
            msg = '{{magenta}}{} {}{{/}}'.format(sender.name, action_args)
            self.game_world.user_hears(receiver, sender, msg)
        elif receiver != sender:
            # TODO allow objects to respond to emote; either special case here
            # like we're doing in say handler or just expect objects to
            # override the emote handler
            pass


    def _say_handler(self, receiver, sender, _, action_args):
        receiver = self.receiver_model.get_by_id(receiver.id)
        sender = self.receiver_model.get_by_id(sender.id)
        if receiver.user_account:
            # TODO pick a color for spoken things
            msg = '{} says, \"{}\"'.format(sender.name, action_args)
            self.game_world.user_hears(receiver, sender, msg)
        elif receiver != sender:
            for hear_pattern, callback in self.hears.items():
                if wildcard_match(hear_pattern, action_args):
                    callback(
                        ProxyGameObject(receiver),
                        ProxyGameObject(sender),
                        action_args)

    def _whisper_handler(self, receiver, sender, _, action_args):
        receiver = self.receiver_model.get_by_id(receiver.id)
        sender = self.receiver_model.get_by_id(sender.id)
        if receiver.user_account:
            msg = '{} whispers so only you can hear: {}'.format(sender.name, action_args)
            self.game_world.user_hears(receiver, sender, msg)

    def add_hears_handler(self, hear_string, fn):
        """This function adds a listener for phrases uttered by mush users (ie,
        not commands).

        For example, if there's a hear handler set up for "*eat*" and a user
        says "i'm eating spaghetti", this callback would trigger.
        """
        self.hears[hear_string] = fn

    def add_provides_handler(self, action, fn):
        self.provides[action] = fn

    def handler(self, game_world, action):
        self._ensure_game_world(game_world)

        return self.provides.get(action, self.noop)

class ScriptedObjectMixin:
    """This database-less class implements the runtime behavior of a tildemush
    object. The GameObject represents all of the stuff that's persisted about a
    game object in the DB.


    THIS CLASS DOES NOT STAND-ALONE. It has hard depdencies on GameObject, and
    is split out to enhance readbility. In general, when working on script
    handling, you aren't interested in a GameObject's persisted data and
    vice-versa.
    """

    @classmethod
    def get_template(cls, obj_type):
        return SCRIPT_TEMPLATES[obj_type]

    @property
    def engine(self):
        # TODO sadness, a circular dependency got introduced here
        # as it is this module is a hack to just save on lines in models.py.
        # models.py should probably just be refactored into a hierarchy of
        # smaller files; until then i'm going to be disgusting and add a
        # .latest_script_rev method to GameObject
        if not hasattr(self, '_engine'):
            self.init_scripting()
        else:
            with get_db().atomic():
                # TODO this looks stupid and weird. Consider some kind of
                # 'live_script_rev' that is probably just an alias for
                # GameObject.script_revision; alternatively, change
                # latest_script_rev to like get_latested_script_rev() or
                # something.
                current_rev = self.script_revision
                latest_rev = self.latest_script_rev
                if latest_rev.id != current_rev.id:
                    try:
                        self.script_revision = latest_rev
                        self.init_scripting()
                    except WitchError as e:
                        self.script_revision = current_rev
                        # TODO log
                    else:
                        self.save()
        return self._engine

    def init_scripting(self):
        if self.script_revision is None:
            self._engine = ScriptEngine(self)
        else:
            try:
                self._engine = self._execute_script(self.script_revision.code)
            except Exception as e:
                raise WitchError(
                    ';_; There is a problem with your witch script: {}'.format(e))

    def handle_action(self, game_world, sender_obj, action, action_args, targets=None):
        self._ensure_world(game_world)
        # TODO to support bindings like $object, the game world has to do:
        # - fuzzy name resolution
        # - mapping of each $ form to a game object
        # - send them to this function via a dict

        if targets is None:
            # TODO unfuck this
            targets = {}

        # TODO wrap each v in targets in a ProxyGameObject

        # TODO there are *horrifying* race conditions going on here if set_data
        # and get_data are used in separate transactions. Call handler inside
        # of a transaction:
        return self.engine.handler(game_world, action)(
                ProxyGameObject(self),
                ProxyGameObject(sender_obj),
                action,
                action_args)

    # say, set_data, get_data, and tell_sender are part of the WITCH scripting
    # API. that should probably be explicit somehow?

    def emote(self, message):
        self.game_world.dispatch_action(self, 'emote', message)

    def say(self, message):
        self.game_world.dispatch_action(self, 'say', message)

    # TODO I may want to forbid getting/setting things not originally declared
    # via ensure_data. This might help newer programmers catch typos in WITCH
    # scripts. For now, eh.
    # lol this would have saved me some debugging earlier when i mixed up - and _
    def set_data(self, key, value):
        self.data[key] = value
        self.save()

    def get_data(self, key, default=None):
        return self.get_by_id(self.id).data.get(key, default)

    def tell_sender(self, sender_obj, action, args):
        self.game_world.dispatch_action(sender_obj, action, args)

    def move_sender(self, sender_obj, direction):
        current_room = sender_obj.room
        route = self.get_data('exit', {}).get(current_room.shortname)
        if route is None or route[0] != direction:
            raise ClientError('illegal move') # this should have been caught higher up, so ok to throw

        self.game_world.move_obj(sender_obj, route[1])

    def teleport_sender(self, sender_obj, target_room_name):
        self.game_world.move_obj(sender_obj, target_room_name)

    def _execute_script(self, witch_code):
        """Given a pile of script revision code, this function prepends the
        (witch) macro definition and then reads and evals the combined code."""
        script_text = self.script_revision.code
        with_header = '{}\n{}'.format(WITCH_HEADER, script_text)
        buff = io.StringIO(with_header)
        stop = False
        result = None
        wi = WitchInterpreter(self)
        while not stop:
            try:
                tree = hy.read(buff)
                witch_ast = hy_compile(tree, '__main__')
                wi.evaluate_ast(witch_ast)
            except EOFError:
                stop = True
        return wi.script_engine

    def _ensure_data(self, data_mapping):
        """Given the default values for some gameobject's script, initialize
        this object's data column to those defaults. Saves the instance."""
        if data_mapping == {}:
            return

        for k,v in data_mapping.items():
            if k not in self.data:
                self.data[k] = v

        self.save()

    def _ensure_world(self, game_world):
        if not hasattr(self, 'game_world'):
            self.game_world = game_world
