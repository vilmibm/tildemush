from datetime import datetime
import json
import re

import bcrypt
import hy
import peewee as pw
from playhouse.signals import Model, pre_save
from playhouse.postgres_ext import JSONField


from . import config

BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12

class ScriptEngine:
    def __init__(self):
        self.handlers = {'debug': self.debug_handler,
                         'say': self.say_handler}

    @staticmethod
    def noop(*args, **kwargs):
        pass

    def debug_handler(self, receiver, sender, cmd_args):
        # TODO i don't even know if this makes sense
        return '{} <- {} with {}'.format(receiver, sender, cmd_args)

    def say_handler(self, receiver, sender, cmd_args):
        # TODO i don't even know if this makes sense
        if receiver.user_account:
            receiver.user_account.hears(cmd_args)

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

class ScriptRevision(BaseModel):
    code = pw.TextField()
    script = pw.ForeignKeyField(Script)

class GameObject(BaseModel):
    # every object needs to tie to a user account for authorizaton purposes

    # so what is the lifecycle of a gameobject?

    # it exists in perpetuity as a row in the DB. its code exists in a
    # ScriptRevision row. Its code isn't necessarily in RAM; if an action
    # occurs near it, we need to know if it responds to a certain action.

    # If its code isn't in RAM, we need to pull and evaluate its WITCH from the
    # DB. The result of that evaluation will exist in RAM. If we've gotten to
    # this point, we know there is an instance of GameObject in RAM.

    # Given a horse object called Snoozy and a player object called Vilmibm:

    # 1. Vilmibm's user account runs "/pet" resulting in "COMMAND pet"
    # 2. GameWorld queries for all of the objects that can "hear" that command, including Snoozy
    # 3. Snoozy's script_engine is asked if it can handle "pet"
    #  a. Snoozy's game object points to a scriptrevision, so we pull it from the DB
    #  b. we run the scriptrevision's WITCH and now have a choice: does it
    #     instantiate a ScriptEngine or does it call methods on the GameObject
    #     instance? It might not matter; on the one hand i like the "code" part of
    #     a GameObject being in its own instance, but it's weird to have it
    #     divorced from the data stored in GameObject. Ultimately, I like that the
    #     (witch) macro is instantiating a new thing: it doesn't need access to an
    #     existing gameobject.
    #     thus: we instantiate and call add_handler on a scriptrevision
    #  c. we now return that, yes, a handler exists for 'pet'
    # 4. Snoozy's 'pet' handler is called and is passed Snoozy (receiver) and the player object (sender)
    #  a. data is fetched, checked, and set via Snoozy's instance
    #  b. Snoozy emits "/say neigh"
    # 5. GameWorld queries for all of the objects that can "hear" Snooy's say, including Vilmibm
    # 6. Vilmibm's handler for "say" runs
    #  a. we check if Vilmibm, the receiver, has a user_account property. If it
    #     does, we call its "hears" method and pass say's arguments.
    #
    # The glaring hole in all this is that we're not dispatching based on
    # argument; in other words, we merely heard that "/pet" happened. This is a
    # big oversight, I think, but I want GameObjects to be able to respond to
    # both transitive and intransitive verbs. For now /pet is intransitive
    # (which is counter intuitive) but I'm kind of desperate to see an
    # end-to-end PoC running with all these parts.

    author = pw.ForeignKeyField(UserAccount)
    name = pw.CharField()
    description = pw.TextField(default='')
    script_revision = pw.ForeignKeyField(ScriptRevision, null=True)
    is_player_obj = pw.BooleanField(default=False)
    data = JSONField(default='{}')

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
            # TODO should this be two steps?
            compiled = self._compile_script()
            self._engine = self._execute_script(compiled)

        return self._engine

    def _compile_script(self):
        script_text = self.script_revision.code
        with_header = '{}\n\n{}'.format(HY_HEADER, script_text)
        return hy.read_str(with_header)

    def _execute_script(self, compiled_code):
        # This evals in current scope, so ScriptEngine is available
        return hy.eval(compiled_code)

    def _ensure_data(self, data_mapping):
        """Given the default values for some gameobject's script, initialize
        this object's data column to those defaults. Saves the instance."""
        if data_mapping == {}:
            return
        if self.data != '{}':
            return
        self.data = json.dumps(data_mapping)
        self.save()

    # TODO should these be _ methods too?
    def say(self, message):
        # TODO use GameWorld to emit a say action?
        print('in say')
        pass

    def set_data(self, key, value):
        self.data.set(key, value)
        self.save()

    def get_data(self, key):
        return self.data.extract(key)

    def handle_action(sender_obj, action, action_args):
        # TODO i'm using, alternately, rest and cmd_args. i should standardize on action_args.
        self.engine.handler(action)(self, sender_obj, rest)

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
