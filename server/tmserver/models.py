from datetime import datetime
import re

import bcrypt
import peewee as pw
from playhouse.signals import Model, pre_save, post_save
from playhouse.postgres_ext import JSONField

from . import config
from .errors import UserValidationError, ClientException
from .scripting import ScriptedObjectMixin


BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12

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

    @classmethod
    def create_scripted_object(self, todo):
        """This function should do the necessary shenanigans to create a
        script/scriptrev/obj. it should accept a script template name and a
        dict of formatting data for the script template."""
        # TODO
        pass

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

    @property
    def player_obj(self):
        return GameObject.get_or_none(
            GameObject.author == self,
            GameObject.is_player_obj == True)

    def __eq__(self, other):
        if not hasattr(other, 'username'):
            return False
        return self.username == other.username

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.username,))


@pre_save(sender=UserAccount)
def pre_user_save(cls, instance, created):
    if not created:
        instance.updated_at = datetime.utcnow()

    if created and instance.password:
        instance._hash_password()


@post_save(sender=UserAccount)
def post_user_save(cls, instance, created):
    if created:
        # TODO set the name/desc in kv data for these objects
        GameObject.create(
            author=instance,
            name=instance.username,
            shortname=instance.username,
            description='a gaseous cloud',
            is_player_obj=True)
        GameObject.create(
            author=instance,
            name="{username}'s Sanctum".format(instance.username),
            description="This is your private space. Only you (and gods) can enter here. Any new rooms you create will be attached to this hub. You are free to store items here for safekeeping that you don't want to carry around.",
            shortname='{}-sanctum'.format(instance.username),
            is_sanctum=True)


class Script(BaseModel):
    author = pw.ForeignKeyField(UserAccount)
    name = pw.CharField()


class ScriptRevision(BaseModel):
    code = pw.TextField()
    script = pw.ForeignKeyField(Script)

@pre_save(sender=ScriptRevision)
def pre_scriptrev_save(cls, instance, created):
    instance.code = instance.code.lstrip().rstrip()


class GameObject(BaseModel, ScriptedObjectMixin):
    author = pw.ForeignKeyField(UserAccount)
    # TODO remove these in favor of data k/v
    name = pw.CharField()
    description = pw.TextField(default='')
    shortname = pw.CharField(null=False, unique=True)
    script_revision = pw.ForeignKeyField(ScriptRevision, null=True)
    is_player_obj = pw.BooleanField(default=False)
    is_sanctum = pw.BooleanField(default=False)
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
