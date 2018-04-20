from datetime import datetime
import re

import bcrypt
import peewee as pw
from playhouse.signals import Model, pre_save

from . import config

BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12

class GameWorld:
    # TODO do i actually want this? i think i do since while area_of_effect
    # could live in UserAccount, this class will also be handling creating and
    # destroying contain relationships. Those methods might should go into
    # Contains, though. I'll keep this here for now until more dust settles.
    @classmethod
    def area_of_effect(cls, user_account):
        """Given a user_account, returns the set of objects that should
        receive events the account emits.
        """
        # We want a set that includes:
        # - the user_account's player object
        # - objects that contain that player object
        # - objects contained by player object
        # - objects contained by objects that contain the player object
        #
        # these four categories can, for the most part, correspond to:
        # - a player of the game
        # - the room a player is in
        # - the player's inventory
        # - objects in the same room as the player
        #
        # thought experiment: the bag
        #
        # my player object has been put inside a bag. The bag _contains_ my
        # player object, and is in a way my "room." it's my conceit that
        # whatever thing contains that bag should not receive the events my
        # player object generates.
        #
        # this is easier to implement and also means you can "muffle" an object
        # by stuffing it into a box.
        room = user_account.player_obj.contained_by
        inventory = set(user_account.player_obj.contains)
        adjacent_objs = set(room.contains)
        return {user_account.player_obj, room} | inventory | adjacent_objs


    # TODO it's arguable these should be defined on Contains
    @classmethod
    def put_into(cls, outer_obj, inner_obj):
        Contains.create(outer_obj=outer_obj, inner_obj=inner_obj)

    @classmethod
    def remove_from(cls, outer_obj, inner_obj):
        Contains.delete().where(
            Contains.outer_obj==outer_obj,
            Contains.inner_obj==inner_obj).execute()


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
    author = pw.ForeignKeyField(UserAccount)
    name = pw.CharField()
    description = pw.TextField(default='')
    script_revision = pw.ForeignKeyField(ScriptRevision, null=True)
    is_player_obj = pw.BooleanField(default=False)

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
