from datetime import datetime
import re

import bcrypt
import peewee as pw

from . import config

BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12


class BaseModel(pw.Model):
    class Meta:
        database = config.get_db()


class UserAccount(BaseModel):
    username = pw.CharField(unique=True)
    display_name = pw.CharField(default='a gaseous cloud')
    password = pw.CharField()
    # TODO add metadata -- created at and updated at

    def hash_password(self):
        self.password = bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt())

    def check_password(self, plaintext_password):
        return bcrypt.checkpw(plaintext_password.encode('utf-8'), self.password.encode('utf-8'))

    # TODO should this be a class method?
    def validate(self):
        if 0 != len(UserAccount.select().where(UserAccount.username == self.username)):
            raise Exception('username taken: {}'.format(self.username))

        if BAD_USERNAME_CHARS_RE.search(self.username):
            raise Exception('username has invalid character')

        if len(self.password) < MIN_PASSWORD_LEN:
            raise Exception('password too short')

class Log(BaseModel):
    env = pw.CharField()
    created_at = pw.DateTimeField(default=datetime.utcnow())
    level = pw.CharField()
    raw = pw.CharField()

MODELS = [UserAccount, Log]
