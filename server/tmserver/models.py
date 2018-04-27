from datetime import datetime
import io
import json
import os
import re

import bcrypt
import hy
import peewee as pw
from playhouse.signals import Model, pre_save
from playhouse.postgres_ext import JSONField

from . import config
from .errors import WitchException

# TODO this is completely bootleg but, inasfar as it's tape and gum and sticks
# it works
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
WITCH_HEADER = None
with open(os.path.join(PKG_DIR, 'witch_header.hy')) as f:
    WITCH_HEADER = f.read()

BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12

class ScriptEngine:
    def __init__(self):
        self.handlers = {'debug': self.debug_handler,
                         'say': self.say_handler}

    @staticmethod
    def noop(*args, **kwargs):
        pass

    def debug_handler(self, receiver, sender, action_args):
        # TODO i don't even know if this makes sense
        return '{} <- {} with {}'.format(receiver, sender, action_args)

    def say_handler(self, receiver, sender, action_args):
        # TODO i don't even know if this makes sense
        if receiver.user_account:
            receiver.user_account.hears(action_args)

    def add_handler(self, action, fn):
        self.handlers[action] = fn

    def handler(self, action):
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
    # TODO
    #
    # so far I've been handling the direction of mutation from a logged in user
    # *into* the gameworld. when it comes time to handle the opposite
    # direction, i need to actually be able to get data to the UserSession from
    # the gameworld. Right now an accout knows nothing about its session. A
    # refactoring is probably in order once i get the first direction going.
    #
    # ODOT

    username = pw.CharField(unique=True)
    display_name = pw.CharField(default='a gaseous cloud')
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
            raise Exception('username taken: {}'.format(self.username))

        if BAD_USERNAME_CHARS_RE.search(self.username):
            raise Exception('username has invalid character')

        if len(self.password) < MIN_PASSWORD_LEN:
            raise Exception('password too short')

    def init_player_obj(self, description=''):
        return GameObject.create(
            author=self,
            name=self.display_name,
            description=description,
            is_player_obj=True)

    @property
    def player_obj(self):
        gos = GameObject.select().where(
            GameObject.author==self,
            GameObject.is_player_obj==True)
        if gos:
            return gos[0]
        return None

    def __eq__(self, other):
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
            # TODO uhh
            pass
        return model_set[0].outer_obj

    @property
    def user_account(self):
        if self.is_player_obj:
            return self.author
        return None

    @property
    def engine(self):
        if not hasattr(self, '_engine'):
            try:
                self._engine = self._execute_script(self.script_revision.code)
            except Exception as e:
                raise WitchException(
                    ';_; There is a problem with your witch script: {}'.format(e))

        return self._engine

    def _execute_script(self, witch_code):
        """Given a pile of script revision code, this function prepends the
        (witch) macro definition and then reads and evals the combined code."""
        # TODO either figure out how to avoid the need or upstream Hy compiler
        # patch that makes this work
        script_text = self.script_revision.code
        with_header = '{}\n{}'.format(WITCH_HEADER, script_text)
        buff = io.StringIO(with_header)
        stop = False
        result = None
        while not stop:
            try:
                tree = hy.read(buff)
                result = hy.eval(tree,
                                 namespace={'ScriptEngine': ScriptEngine},
                                 module_name='tmserver.models')
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

    # TODO should these be _ methods too?
    def say(self, message):
        # TODO use GameWorld to emit a say action?
        print('in say')

    # TODO I may want to forbid getting/setting things not originally declared
    # via ensure_data. This might help newer programmers catch typos in WITCH
    # scripts. For now, eh.
    def set_data(self, key, value):
        self.data[key] = value
        self.save()

    def get_data(self, key):
        return self.get_by_id(self.id).data.get(key)

    def handle_action(self, sender_obj, action, action_args):
        # TODO there are *horrifying* race conditions going on here if set_data
        # and get_data are used in separate transactions. Call handler inside
        # of a transaction:
        return self.engine.handler(action)(self, sender_obj, action_args)

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
    #created_at = pw.DateTimeField(default=datetime.utcnow())
    level = pw.CharField()
    raw = pw.CharField()


MODELS = [UserAccount, Log, GameObject, Contains, Script, ScriptRevision]
