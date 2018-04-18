from datetime import datetime
import re

import bcrypt
import peewee as pw
from playhouse.postgres_ext import JSONField

from . import config

BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12


class BaseModel(pw.Model):
    class Meta:
        database = config.get_db()


# TODO I'm growing concerned about coupling accounts with a thing that exists
# in the game world.
class User(BaseModel):
    username = pw.CharField(unique=True)
    display_name = pw.CharField(default='a gaseous cloud')
    password = pw.CharField()
    # TODO add metadata -- created at and updated at

    ## Data methods
    def hash_password(self):
        self.password = bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt())

    def check_password(self, plaintext_password):
        return bcrypt.checkpw(plaintext_password.encode('utf-8'), self.password.encode('utf-8'))

    # TODO should this be a class method?
    def validate(self):
        if 0 != len(User.select().where(User.username == self.username)):
            raise Exception('username taken: {}'.format(self.username))

        if BAD_USERNAME_CHARS_RE.search(self.username):
            raise Exception('username has invalid character')

        if len(self.password) < MIN_PASSWORD_LEN:
            raise Exception('password too short')


    ## Game methods
    @property
    def inventory(self):
        return (inv.obj for inv in Inventory.select().where(Inventory.user==self))

    def create_object(self, name, description='', script_name=None):
        if not name:
            raise ValueError('objects need a name')
        # TODO find script if supplied, pin revision if needed
        # TODO pin revision
        obj = Object.create(
            name=name,
            description=description,
            creator=self)
        Inventory.create(user=self, obj=obj)
        return obj

    def pickup(self, obj):
        inv = Inventory.select().where(Inventory.obj==obj)
        if inv and inv[0].user == self:
            raise ValueError('you already posess {}'.format(obj.name))
        if inv:
            raise ValueError('cannot get something already owned')
        if obj.anchored and (obj.creator != self):
            raise ValueError('cannot pick up anchored object you did not create')
        Inventory.create(user=self, obj=obj)

    ## Util

    def __str__(self):
        return 'User<{}>'.format(self.username)


class Log(BaseModel):
    env = pw.CharField()
    created_at = pw.DateTimeField(default=datetime.utcnow)
    level = pw.CharField()
    raw = pw.CharField()

class Room(BaseModel):
    creator = pw.ForeignKeyField(User, backref='scripts')
    created_at = pw.DateTimeField(default=datetime.utcnow)

class Script(BaseModel):
    creator = pw.ForeignKeyField(User, backref='scripts')
    created_at = pw.DateTimeField(default=datetime.utcnow)

class ScriptRevision(BaseModel):
    script = pw.ForeignKeyField(Script, backref='revisions')
    code = pw.TextField()
    data = JSONField()

class Object(BaseModel):
    creator = pw.ForeignKeyField(User, backref='created_objects')
    created_at = pw.DateTimeField(default=datetime.utcnow)
    name = pw.CharField(null=False)
    description = pw.TextField()
    scriptrev = pw.ForeignKeyField(ScriptRevision, null=True)
    script = pw.ForeignKeyField(Script, null=True)

    def __str__(self):
        s =  'Object<{}> created by {}'.format(self.name, self.creator)
        if self.owner:
            s = '{} and owned by {}'.format(s, self.owner)
        return s

    @property
    def anchored(self):
        p = Placement.select().where(
            Placement.obj==self)
        if not p:
            return False
        return p[0].anchored

    @property
    def owner(self):
        i = Inventory.select().where(Inventory.obj==self)
        if not i:
            return None
        return i[0].user

class Contain(BaseModel):
    outer_obj = pw.ForeignKeyField(Object)
    inner_obj = pw.ForeignKeyField(Object)

class Inventory(BaseModel):
    user = pw.ForeignKeyField(User)
    obj = pw.ForeignKeyField(Object)

class Location(BaseModel):
    user = pw.ForeignKeyField(User)
    room = pw.ForeignKeyField(Room)

class Placement(BaseModel):
    obj = pw.ForeignKeyField(Object)
    room = pw.ForeignKeyField(Room)
    anchored = pw.BooleanField(default=False)

class Exit(BaseModel):
    room_a = pw.ForeignKeyField(Room)
    room_b = pw.ForeignKeyField(Room)
    direction = pw.CharField()
    reverse_direction = pw.CharField()

MODELS = [User, Log, Object, Room, Script, ScriptRevision, Location, Placement, Inventory, Exit]
