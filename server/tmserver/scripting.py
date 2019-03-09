from fnmatch import fnmatch
import io
import random
import re

import asteval
import hy
from hy.compiler import hy_compile

from .config import get_db
from .errors import ClientError, WitchError
from .util import split_args, ARG_RE_RAW, clean_str

WITCH_HEADER = '(require [tmserver.witch_header [*]])'
ERROR_CLEANUP_RE = re.compile(r' in expr=.*$')

# Note an awful thing here; since we call .format on the script templates, we
# have to escape the WITCH macro's {}. {{}} is not the Hy that we want, but we
# need it in the templates.
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
      (provides "touch $this"
        (teleport-sender (get-data "target"))))
    '''}


def wildcard_match(pattern, string):
    """This is pretty silly, but it's a small wrapper around fnmatch for
    matching wildcarded strings (as opposed to regexes). For now just using
    fnmatch seems fine even if we aren't actually matching filenames. lulz."""
    return fnmatch(string, pattern)

def random_number(a=None, b=None):
    if a is None:
        # nothing passed. use default bounds.
        a = 1
        b = 10
    elif b is None:
        # a was set but not b, that means we have a max and need a min
        b = a
        a = 1

    if b < a:
        # the user must be confused. just use the numbers as a range.
        a,b = b,a

    return random.randint(a, b)

class ProxyGameObject:
    def __init__(self, game_object):
        self.id = game_object.id
        self.shortname = game_object.shortname
        self.name = game_object.name

    def __eq__(self, other):
        return self.id == other.id

# TODO
# (every) macro
# 
# this macro is invoked like:
# (every (random-number)
#   (does "dances"))
# 
# when compiled, a helper (add-scheduled-callback) is called.
# this helper is responsible for storing a row via the ScheduledCallback model as well as storing
# the callback in memory with a generated callback_id.
# if add-scheduled-callback sees that a row exists such that:
# - the revision ID matches the current object revision
# - the hash of the callback matches the current callback's hash
# then it does nothing
#
# the row is something like:
# - last_run timestamp
# - callback_id
# - callback hash
# - object id
# - interval in minutes
# - revision_id
# 
# a scheduler loop runs every minute, looking for rows such that:
#
# last_run + interval <= now
#
# the scheduler then does some stuff.
# - grabs the associated object
# - compiles the witch code
# - runs the callback ID'd by callback_id
#
# questsions / scenarios
#
# - what happens when the server restarts?
#   - nothing, really. the scheduler is started and acts as normal. there will be a thundering herd
#     of unrun tasks at first which might end up being a problem, but i can worry about that later;
#     one tactic is to just set last_run to be the moment the scheduler starts.

# - what about variable intervals?
#  - this is hard to support since it means also supporting a reference to arbitrary code that will
#    evaluate into an interval and re-running it each time the job runs. for the intial support of
#    (every) i'm more comfortable supporting a compile time interval. a hacky way to support this
#    could be having (every) report what the *next* interval is every time it is evaluated but i
#    don't want to depend on that.

# - how will callback hashing work?
#  - I don't ever want a hash across the whole (incantation) as the data section doesn't correspond
#    to revisions. i think i want a hash of everything in (every...). MD5 is what i'd usually use. i'm
#    concerned about a higher collision rate for smaller strings but until that starts happening i
#    want to use something very standard.

# - should hash just be the callback id?
#  - this is kind of instinct but i'm thinking no. ID can be UUID and hash is a seperate concept.

# - how does the scheduler run?
#  - can use the async loop or just run a loop in a thread. for conceptual simplicity i think i'll
#    just use async. in general i want to be taking better advantage of async stuff anyway.

# - are you going to end up leaking memory like crazy as objects with scheduled tasks get reified
#   every minute?
#   - probably ugh i'd like to audit the GameObject lifecycle.
#   - i'll need to study RAM usage over time to really understand it, but right now there shouldn't
#     be risk to constantly re-evaluate the WITCH code. it's already happening pretty much every time
#     anything happens on the server (probably causing a lot of the latency) and when i optimize it
#     it'll optimize for (every) usage as well as regular action dispatching.
#
# - how are tasks stopped?
#   - by deleting them from the WITCH code. upon compilation, after registering callbacks for the
#     current revision all rows for any older revision are deleted.
#
# development plan
#
# - [ ] add model
# - [ ] write and test the add_scheduled_action helper
# - [ ] add (every) macro
# - [ ] add scheduler loop
# - [ ] add server start-up behavior (setting last run)
# - [ ] implement and test (every) hashing
# - [ ] tie is all together as needed
# ODOT

class WitchInterpreter:
    def __init__(self, receiver_model):
        script_engine = ScriptEngine(receiver_model)

        def add_hears_handler(hear_string, callback):
            nonlocal script_engine
            script_engine.add_hears_handler(hear_string, callback)

        def add_sees_handler(see_string, callback):
            nonlocal script_engine
            script_engine.add_sees_handler(see_string, callback)

        def add_provides_handler(action, callback):
            nonlocal script_engine
            script_engine.add_provides_handler(action, callback)

        def add_scheduled_task(interval, units, cb):
            nonlocal receiver_model
            GameWorld.add_scheduled_task(receiver_model, interval, units, cb)

        def set_data(key, value):
            nonlocal receiver_model
            if len(receiver_model.editing_set) == 0:
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

        # ADDING A NEW WITCH API FUNCTION?
        # This is the place to start. usersyms is what is exposed to WITCH programmers. Be mindful
        # what you expose here: it should only be functions that act as closures over sensitive
        # objects.
        #
        # Not all of these are intended to be used directly; stuff like add_hears_handler is called
        # from a convenience macro, (hears).
        #
        # Decide how you want to expose stuff to the user: can it just be a regular function defined
        # here or is it a helper for a macro? If you are providing something that takes code from
        # the user to be used as a callback, you're going to want to wrap it in a macro. If it's a
        # simple function like (random-number), just define it as a function here.
        self.script_engine = script_engine
        self.interpreter = asteval.Interpreter(
            use_numpy=False,
            max_time=100000.0,  # there's a bug with this and setting it arbitrarily high avoids it
            usersyms=dict(
                open=witch_open,
                split_args=split_args,
                random_number=random_number,
                add_scheduled_task=add_scheduled_task,
                add_provides_handler=add_provides_handler,
                add_hears_handler=add_hears_handler,
                add_sees_handler=add_sees_handler,
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
        self.sees = {}
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
            for see_pattern, callback in self.sees.items():
                if wildcard_match(see_pattern, action_args):
                    callback(
                        ProxyGameObject(receiver),
                        ProxyGameObject(sender),
                        action_args)

    def _say_handler(self, receiver, sender, _, action_args):
        receiver = self.receiver_model.get_by_id(receiver.id)
        sender = self.receiver_model.get_by_id(sender.id)
        if receiver.user_account:
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

    def add_sees_handler(self, see_string, fn):
        """
        This function adds a listener for actions taken by users via the /emote command. For
        example, if a user runs:

        /emote dances wildly

        then a magic cupboard might choose to dance along with them

        Magic Cupboard dances along with vilmibm!
        """
        self.sees[see_string] = fn

    def add_provides_handler(self, action, fn):
        self.provides[action] = fn

    def handler(self, game_world, receiver, action, action_args):
        """
        This method is confusing. Its purpose is to map from a given action and arguments to a
        callable, additionally noting if the callable is acting transitively.

        Part of this process is parsing the $this placeholder in action handler definitions in WITCH
        code (how we determine if a given handler is transitive).
        """
        self._ensure_game_world(game_world)

        transitively_handled = False

        # Look for transitive handling

        found = None
        for provides_str in self.provides.keys():
            if provides_str.startswith(action) and '$this' in provides_str:
                found = provides_str
                break

        if found:
            # This can and probably should be memoized.
            as_regex = re.compile(found.replace('$this', ARG_RE_RAW))

            to_match = '{} {}'.format(action, action_args)

            obj_name_match = as_regex.match(to_match)

            if obj_name_match is not None:
                if receiver.fuzzy_match(clean_str(obj_name_match[1])):
                    transitively_handled = True
                    return transitively_handled, self.provides[found]

        # fall back on intransitive handling
        return transitively_handled, self.provides.get(action, self.noop)

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
        # TODO #191 sadness, a circular dependency got introduced here
        # as it is this module is a hack to just save on lines in models.py.
        # models.py should probably just be refactored into a hierarchy of
        # smaller files; until then i'm going to be disgusting and add a
        # .latest_script_rev method to GameObject
        if not hasattr(self, '_engine'):
            self.init_scripting()
        else:
            with get_db().atomic():
                current_rev = self.script_revision
                latest_rev = self.latest_script_rev
                if latest_rev.id != current_rev.id:
                    try:
                        self.script_revision = latest_rev
                        self.init_scripting()
                        self.prune_scheduled_tasks()
                    except WitchError as e:
                        self.script_revision = current_rev
                        # TODO #180 log
                    else:
                        self.save()
        return self._engine

    def init_scripting(self, use_db_data=True):
        if self.script_revision is None:
            self._engine = ScriptEngine(self)
        else:
            try:
                self._engine = self._execute_script(self.get_code(use_db_data))
            except Exception as e:
                raise WitchError(
                    ';_; There is a problem with your witch script: {}'.format(e))

    def handle_action(self, game_world, sender_obj, action, action_args):
        self._ensure_world(game_world)
        is_transitive, handler = self.engine.handler(game_world, self, action, action_args)

        return is_transitive, handler(ProxyGameObject(self),
                                      ProxyGameObject(sender_obj),
                                      action,
                                      action_args)

    # say, set_data, get_data, and tell_sender are part of the WITCH scripting
    # API. that should probably be explicit somehow?

    def emote(self, message):
        self.game_world.dispatch_action(self, 'emote', message)

    def say(self, message):
        self.game_world.dispatch_action(self, 'say', message)

    def set_data(self, key, value):
        hm = self.get_by_id(self.id)
        hm.data[key] = value
        hm.save()

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
        with_header = '{}\n{}'.format(WITCH_HEADER, witch_code)
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
        """Given the kv values from some gameobject's script, (re)initialize
        this object's data column to those values. Saves the instance."""
        self.data = data_mapping

        self.save()

    def _ensure_world(self, game_world):
        if not hasattr(self, 'game_world'):
            self.game_world = game_world
