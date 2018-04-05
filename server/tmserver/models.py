import bcrypt
import peewee as pw

from . import config


class BaseModel(pw.Model):
    class Meta:
        database = config.get_db()


class User(BaseModel):
    username = pw.CharField(unique=True)
    display_name = pw.CharField(default='a gaseous cloud')
    password = pw.CharField()
    # TODO add metadata -- created at and updated at 

    def hash_password(self):
        self.password = bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt())

    def check_password(self, plaintext_password):
        return bcrypt.checkpw(plaintext_password.encode('utf-8'), self.password.encode('utf-8'))

    def validate(self):
        # TODO username characters, length
        # TODO password length, dictionary words
        pass

MODELS = [User,]
