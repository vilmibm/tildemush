from datetime import datetime
import itertools
import re

import bcrypt
import peewee as pw
from hy.contrib.hy_repr import hy_repr
from playhouse.signals import Model, pre_save, post_save
from playhouse.postgres_ext import JSONField, IntervalField

from . import config
from .errors import UserValidationError, ClientError
from .scripting import ScriptedObjectMixin
from .util import strip_color_codes, collapse_whitespace


HAS_RE = re.compile(r'\(has .+?\)', re.S)
BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12

class BaseModel(Model):
    created_at = pw.DateTimeField(default=datetime.utcnow)
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
    is_god = pw.BooleanField(default=False)

    def _hash_password(self):
        self.password = bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt())

    def check_password(self, plaintext_password):
        pw = self.password
        if type(self.password) == type(''):
            pw = self.password.encode('utf-8')
        return bcrypt.checkpw(plaintext_password.encode('utf-8'), pw)

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
def on_user_account_create(cls, instance, created):
    if not created: return

    with config.get_db().atomic():
        player = GameObject.create_scripted_object(
            instance, instance.username, 'player',
            {'name': instance.username,
            'description': 'a gaseous cloud'})
        player.is_player_obj = True
        player.save()
        sanctum = GameObject.create_scripted_object(
            instance, '{}/sanctum'.format(instance.username), 'room',
            dict(name="{}'s Sanctum".format(instance.username),
                 description="""This is your private space. Only you (and gods)
                 can enter here. Any new rooms you create will be attached to
                 this hub. You are free to store items here for safekeeping
                 that you don't want to carry around."""))
        sanctum.is_sanctum=True,
        sanctum.save()


class Script(BaseModel):
    author = pw.ForeignKeyField(UserAccount)
    name = pw.CharField()


class ScriptRevision(BaseModel):
    code = pw.TextField()
    script = pw.ForeignKeyField(Script)

    def __lt__(self, other_revision):
        return self.created_at < other_revision.created_at

    def __gt__(self, other_revision):
        return self.created_at > other_revision.created_at


@pre_save(sender=ScriptRevision)
def pre_scriptrev_save(cls, instance, created):
    instance.code = instance.code.strip()


class Permission(BaseModel):
    """There are four types of permissions for a game object: read, write,
    carry, and execute.

    Each one has two states: owner or world.

    Read and write control who can view and update an object's WITCH code.

    Carry controls who can pick up an object.

    Execute controls who can send actions to an object.

    The default set of permissions is:

    W+R O+W W+C W+C
    """
    PERMISSIONS = ['read', 'write', 'carry', 'execute']
    VALUES = ['owner', 'world']

    OWNER = 1
    WORLD = 2

    read = pw.IntegerField(default=WORLD)
    write = pw.IntegerField(default=OWNER)
    carry = pw.IntegerField(default=WORLD)
    execute = pw.IntegerField(default=WORLD)

    @classmethod
    def valid_perm(cls, perm):
        return perm in cls.PERMISSIONS

    @classmethod
    def valid_value(cls, value):
        return value in cls.VALUES

    @classmethod
    def _enum_to_str(cls, perm):
        return 'world' if perm == cls.WORLD else 'owner'

    def as_dict(self):
        return dict(
            read=self._enum_to_str(self.read),
            write=self._enum_to_str(self.write),
            carry=self._enum_to_str(self.carry),
            execute=self._enum_to_str(self.execute))


class GameObject(BaseModel, ScriptedObjectMixin):
    author = pw.ForeignKeyField(UserAccount)
    shortname = pw.CharField(null=False, unique=True)
    script_revision = pw.ForeignKeyField(ScriptRevision, null=True)
    is_player_obj = pw.BooleanField(default=False)
    is_sanctum = pw.BooleanField(default=False)
    data = JSONField(default=dict)
    perms = pw.ForeignKeyField(Permission, backref='obj', null=True)

    @classmethod
    def create_scripted_object(cls, author, shortname, obj_type='item', format_dict=None):
        """This function does the necessary shenanigans to create a
        script/scriptrev/obj. It creates them all in the DB and returns the
        GameObject."""

        if format_dict is None:
            format_dict = {
                'name': 'an object',
                'description': 'a perfect gray sphere',
            }

        format_dict['author'] = author.username

        if 'description' in format_dict:
            format_dict['description'] = collapse_whitespace(format_dict['description'])

        script_code = cls.get_template(obj_type).format(**format_dict)
        with config.get_db().atomic():
            script = Script.create(
                author=author,
                name=shortname)
            scriptrev = ScriptRevision.create(
                script=script,
                code=script_code)
            game_obj = GameObject.create(
                perms=Permission(),
                author=author,
                shortname=shortname,
                script_revision=scriptrev)
            game_obj.init_scripting(use_db_data=False)

        return game_obj

    @property
    def name(self):
        return self.get_data('name', self.shortname)

    @property
    def description(self):
        return self.get_data('description', '')

    @property
    def contains(self):
        return (c.inner_obj for c in Contains.select().where(Contains.outer_obj==self))

    @property
    def contained_by(self):
        """Returns a generator of all the objects that contain the calling
        object."""
        return (c.outer_obj for c in Contains.select().where(Contains.inner_obj==self))

    @property
    def neighbors(self):
        """Returns generator of the objects contained by this object's container."""
        return itertools.chain(*[o.contains for o in self.contained_by])

    @property
    def room(self):
        """Unlike contained_by, this method either returns the single thing
        that contains the calling obj or raises."""
        model_set = list(Contains.select().where(Contains.inner_obj==self))
        if not model_set:
            return None
        if len(model_set) > 1:
            raise ClientError("Bad state: room() called but obj contained by multiple things.")
        return model_set[0].outer_obj


    @property
    def user_account(self):
        if self.is_player_obj:
            return self.author
        return None

    @property
    def latest_script_rev(self):
        current_rev = self.script_revision
        return ScriptRevision\
            .select()\
            .where(ScriptRevision.script==current_rev.script)\
            .order_by(ScriptRevision.created_at.desc())\
            .limit(1)[0]

    def get_code(self, use_db_data=True):
        code = None
        if use_db_data:
            code = self.latest_script_rev.code
            as_hy = '(has {})'.format(hy_repr(self.data))
            code = HAS_RE.sub(as_hy, code)
        else:
            code = self.latest_script_rev.code

        return code

    def set_perm(self, perm, setting):
        """Given a perm defined in Permission and either 'owner' or 'world',
        sets and saves the permission on the game object."""
        if not hasattr(self.perms, perm):
            raise ValueError('Invalid permission {}'.format(perm))
        if not hasattr(self.perms, setting.upper()):
            raise ValueError('Invalid permission mode {}'.format(setting))

        setattr(self.perms, perm, getattr(self.perms, setting.upper()))
        self.perms.save()

    def set_perms(self, **kwargs):
        for k,v in kwargs.items():
            self.set_perm(k, v)

    def fuzzy_match(self, match_string):
        """Given a string, return whether or not it could be considered as
        referencing this object. Roughly, this means:

        - is it an exact match on shortname?
        - is it an exact match on name?
        - is it a prefix for name?
        - is it a prefix for shortname?
        - does it appear as a substring in name?
        - does it appear as a substring in shortname?

        In all cases, case is ignored.
        """
        shortname = self.shortname.lower()
        name = strip_color_codes(self.name.lower())
        match_string = match_string.lower()
        if match_string == shortname:
            return True

        if match_string == name:
            return True

        if name.startswith(match_string):
            return True

        if shortname.startswith(match_string):
            return True

        if match_string in name:
            return True

        if match_string in shortname:
            return True

        return False

    def can_carry(self, target_obj):
        return self._can_perm('carry', target_obj)

    def can_read(self, target_obj):
        return self._can_perm('read', target_obj)

    def can_write(self, target_obj):
        return self._can_perm('write', target_obj)

    def can_execute(self, target_obj):
        return self._can_perm('execute', target_obj)

    def _can_perm(self, perm, target_obj):
        return self.author == target_obj.author\
               or getattr(target_obj.perms, perm) == Permission.WORLD

    def prune_scheduled_tasks(self):
        ScheduledTask.delete().where(ScheduledTask.revision < self.latest_script_rev).execute()

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'GameObject<{}>'.format(self.shortname)

    def __eq__(self, other):
        return self.shortname == other.shortname

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.author.username, self.shortname))


@post_save(sender=GameObject)
def on_game_object_create(cls, instance, created):
    if not created: return
    instance.perms = Permission.create()
    instance.save()

class Editing(BaseModel):
    user_account = pw.ForeignKeyField(UserAccount)
    game_obj = pw.ForeignKeyField(GameObject)


class Contains(BaseModel):
    outer_obj = pw.ForeignKeyField(GameObject)
    inner_obj = pw.ForeignKeyField(GameObject)


class LastSeen(BaseModel):
    user_account = pw.ForeignKeyField(UserAccount)
    room = pw.ForeignKeyField(GameObject)


class Log(BaseModel):
    env = pw.CharField()
    level = pw.CharField()
    raw = pw.CharField()


class ScheduledTask(BaseModel):
    obj = pw.ForeignKeyField(GameObject)
    revision = pw.ForeignKeyField(ScriptRevision)
    interval = IntervalField() # seconds
    last_run = pw.DateTimeField(default=datetime.utcnow)
    cbhash = pw.TextField()

    # I want some protection against a long running or stuck job. perhaps a field like last_elapsed;
    # it's nil'd at the start of a task execution? that is trying to pack too much info into one
    # field; how would i know when a task has never been run? i guess if last_run is nil...
    #
    # i'm essentially rebuilding something like celery. should i just use celery?
    #
    # no; because the code is going to have to be hot reloaded. celery needs to reboot workers to
    # pull in the new tasks. i want to avoid that.
    #
    # so what are the bronze path cases i'm concerned about?
    #
    # - task fails repeatedly
    #   - by "fail" i mean "throws an exception." it's going to be impossible to tell if a task is
    #   throwing an exception *every* time or intermittently without a lot of analysis; i think a
    #   perpetually failing task just needs to be clearly logged and accepted. it can be manually
    #   cleared out if an admin desires.
    # - task has infinite loop
    #   - tasks are called with a timeout -- they have to run within 45 seconds. a perpetually
    #   timing out task, i think, is essentially just the previous acceptably-infinite failure case.
    # - task is started but is already running
    #   - i think if last_run is set at the *start* of the callback, this is avoided. the timeout is
    #   less than the interval
    #  

MODELS = [UserAccount, Log, GameObject, Contains, Script, ScriptRevision, Permission, Editing,
          LastSeen, ScheduledTask]
