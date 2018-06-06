from datetime import datetime
import io
import json
import os
import re

import bcrypt
import hy
import peewee as pw
from playhouse.signals import Model, pre_save, post_save
from playhouse.postgres_ext import JSONField

from . import config
from .errors import WitchException, UserValidationError, ClientException

WITCH_HEADER = '(require [tmserver.witch_header [*]])'

BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12

class ScriptEngine:
    CONTAIN_TYPES = {'acquired', 'entered', 'lost', 'freed'}
    def __init__(self):
        self.handlers = {'debug': self._debug_handler,
                         'contain': self._contain_handler,
                         'say': self._say_handler,
                         'announce': self._announce_handler,
                         'whisper': self._whisper_handler}

    @staticmethod
    def noop(*args, **kwargs):
        pass

    def _ensure_game_world(self, game_world):
        if not hasattr(self, 'game_world'):
            self.game_world = game_world

    def _debug_handler(self, receiver, sender, action_args):
        return '{} <- {} with {}'.format(receiver, sender, action_args)

    def _contain_handler(self, receiver, sender, action_args):
        contain_type = action_args
        if contain_type not in self.CONTAIN_TYPES:
            raise ClientException('Bad container relation: {}'.format(contain_type))
        if receiver.user_account:
            receiver.user_account.send_client_update(self.game_world)
            # TODO we actually want the client to show messages about these
            # events, i think. we can implement that once we actually implement
            # movement and inventory commands. until then we just care that the
            # client_state payload is sent.

    def _announce_handler(self, receiver, sender, action_args):
        if receiver.user_account:
            msg = "The very air around you seems to shake as {}'s booming voice says {}".format(
                sender.name, action_args)
            receiver.user_account.hears(self.game_world, sender, msg)

    def _say_handler(self, receiver, sender, action_args):
        if receiver.user_account:
            msg = '{} says, \"{}\"'.format(sender.name, action_args)
            receiver.user_account.hears(self.game_world, sender, msg)

    def _whisper_handler(self, receiver, sender, action_args):
        if receiver.user_account:
            msg = '{} whispers so only you can hear: {}'.format(sender.name, action_args)
            receiver.user_account.hears(self.game_world, sender, msg)

    def add_handler(self, action, fn):
        self.handlers[action] = fn

    def handler(self, game_world, action):
        self._ensure_game_world(game_world)
        return self.handlers.get(action, self.noop)

class BaseModel(Model):
    created_at = pw.DateTimeField(default=datetime.utcnow())
    class Meta:
        database = config.get_db()

class UserAccount(BaseModel):
    """This model represents the bridge between the game world (a big tree of
    objects) and a live conncetion from a game client. A user account doesn't
    "exist," per se, in the game world, but rather is anchored to a single
    "player" object. this player object is the useraccount's window on the game
    world."""

    username = pw.CharField(unique=True)
    password = pw.CharField()
    updated_at = pw.DateTimeField(null=True)
    god = pw.BooleanField(default=False)

    def _hash_password(self):
        self.password = bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt())

    def check_password(self, plaintext_password):
        pw = self.password
        if type(self.password) == type(''):
            pw = self.password.encode('utf-8')
        return bcrypt.checkpw(plaintext_password.encode('utf-8'), pw)

    # TODO should this be a class method?
    # TODO should this just run in pre_save?
    def validate(self):
        if 0 != len(UserAccount.select().where(UserAccount.username == self.username)):
            raise UserValidationError('username taken: {}'.format(self.username))

        if BAD_USERNAME_CHARS_RE.search(self.username):
            raise UserValidationError('username has invalid character')

        if len(self.password) < MIN_PASSWORD_LEN:
            raise UserValidationError('password too short')

    def _init_player_obj(self, description='a gaseous cloud'):
        GameObject.create(
            author=self,
            name=self.username,
            description=description,
            is_player_obj=True)

    def hears(self, game_world, sender_obj, message):
        game_world.get_session(self.id).handle_hears(sender_obj, message)

    def send_client_update(self, game_world):
        if game_world.is_connected(self.id):
            game_world.get_session(self.id).handle_client_update(game_world.client_state(self))

    @property
    def player_obj(self):
        gos = GameObject.select().where(
            GameObject.author==self,
            GameObject.is_player_obj==True)
        if gos:
            return gos[0]
        return None

    def __eq__(self, other):
        if not hasattr(other, 'username'):
            return False
        return self.username == other.username

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.username,))

@pre_save(sender=UserAccount)
def pre_save_handler(cls, instance, created):
    if not created:
        instance.updated_at = datetime.utcnow()

    if created and instance.password:
        instance._hash_password()


@post_save(sender=UserAccount)
def post_save_handler(cls, instance, created):
    if created:
        instance._init_player_obj()


class Script(BaseModel):
    author = pw.ForeignKeyField(UserAccount)
    name = pw.CharField()

class ScriptRevision(BaseModel):
    code = pw.TextField()
    script = pw.ForeignKeyField(Script)

class GameObject(BaseModel):
    author = pw.ForeignKeyField(UserAccount)
    name = pw.CharField()
    description = pw.TextField(default='')
    script_revision = pw.ForeignKeyField(ScriptRevision, null=True)
    is_player_obj = pw.BooleanField(default=False)
    data = JSONField(default=dict)

    @property
    def contains(self):
        return (c.inner_obj for c in Contains.select().where(Contains.outer_obj==self))

    @property
    def contained_by(self):
        model_set = list(Contains.select().where(Contains.inner_obj==self))
        if not model_set:
            return None
        if len(model_set) > 1:
            raise ClientException("Bad state: contained by multiple things.")
        return model_set[0].outer_obj

    @property
    def user_account(self):
        if self.is_player_obj:
            return self.author
        return None

    @property
    def engine(self):
        if not hasattr(self, '_engine'):
            if self.script_revision is None:
                self._engine = ScriptEngine()
            else:
                try:
                    self._engine = self._execute_script(self.script_revision.code)
                except Exception as e:
                    raise WitchException(
                        ';_; There is a problem with your witch script: {}'.format(e))

        return self._engine

    def _execute_script(self, witch_code):
        """Given a pile of script revision code, this function prepends the
        (witch) macro definition and then reads and evals the combined code."""
        script_text = self.script_revision.code
        with_header = '{}\n{}'.format(WITCH_HEADER, script_text)
        buff = io.StringIO(with_header)
        stop = False
        result = None
        while not stop:
            try:
                tree = hy.read(buff)
                result = hy.eval(tree,
                                 namespace={'ScriptEngine': ScriptEngine})
            except EOFError:
                stop = True
        return result

    def _ensure_data(self, data_mapping):
        """Given the default values for some gameobject's script, initialize
        this object's data column to those defaults. Saves the instance."""
        if data_mapping == {} or self.data != {}:
            return
        self.data = data_mapping
        self.save()

    def _ensure_world(self, game_world):
        if not hasattr(self, 'game_world'):
            self.game_world = game_world

    # TODO should these be _ methods too?
    def say(self, message):
        self.game_world.dispatch_action(self, 'say', message)

    # TODO I may want to forbid getting/setting things not originally declared
    # via ensure_data. This might help newer programmers catch typos in WITCH
    # scripts. For now, eh.
    # lol this would have saved me some debugging earlier when i mixed up - and _
    def set_data(self, key, value):
        self.data[key] = value
        self.save()

    def get_data(self, key):
        return self.get_by_id(self.id).data.get(key)

    def handle_action(self, game_world, sender_obj, action, action_args):
        self._ensure_world(game_world)
        # TODO there are *horrifying* race conditions going on here if set_data
        # and get_data are used in separate transactions. Call handler inside
        # of a transaction:
        return self.engine.handler(game_world, action)(self, sender_obj, action_args)

    # containership methods
    # TODO this naming sucks
    def put_into(self, inner_obj):
        if inner_obj.contained_by:
            inner_obj.contained_by.remove_from(inner_obj)
        Contains.create(outer_obj=self, inner_obj=inner_obj)

    def remove_from(self, inner_obj):
        Contains.delete().where(
            Contains.outer_obj==self,
            Contains.inner_obj==inner_obj).execute()

    def __str__(self):
        return 'GameObject<{}> authored by {}'.format(self.name, self.author)

    def __eq__(self, other):
        script_revision = -1
        other_revision = -1
        if self.script_revision:
            script_revision = self.script_revision.id
        if other.script_revision:
            other_revision = other.script_revision.id

        return self.author.username == other.author.username\
            and self.name == other.name\
            and script_revision == other_revision

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        script_revision = -1
        if self.script_revision:
            script_revision = self.script_revision.id

        return hash((self.author.username, self.name, script_revision))

class Contains(BaseModel):
    outer_obj = pw.ForeignKeyField(GameObject)
    inner_obj = pw.ForeignKeyField(GameObject)


class Log(BaseModel):
    env = pw.CharField()
    level = pw.CharField()
    raw = pw.CharField()


MODELS = [UserAccount, Log, GameObject, Contains, Script, ScriptRevision]
