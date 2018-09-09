import peewee as pw
import playhouse.migrate as m

from .config import get_db
from .models import MODELS, GameObject, UserAccount
import logging

def logging_env_column(db, migrator):
    m.migrate(
        migrator.add_column('log', 'env', pw.CharField(null=True))
    )

def logging_remove_actor_column(db, migrator):
    m.migrate(
        migrator.drop_column('log', 'actor_id'))

# These are largely historical, but may be of use once there exists a
# long-running tildemush instance. in test and dev, i'm repeatedly trashing the
# db with reset_db.
MIGRATIONS = [
    logging_env_column,
    logging_remove_actor_column
]

def initialize():
    get_db().create_tables(MODELS)

def migrate(migrations=MIGRATIONS):
    db = get_db()
    migrator = m.PostgresqlMigrator(db)
    for migration in migrations:
        migration(db, migrator)

def init_db():
    get_db().create_tables(MODELS, safe=True)
    logging.getLogger('tmserver').info("db tables: {}".format(get_db().get_tables()))

    if 0 == UserAccount.select().where(UserAccount.username=='god').count():
         UserAccount.create(
            username='god',
            password='TODO',  # TODO set from config
            is_god=True)

    if 0 == GameObject.select().where(GameObject.shortname=='god/foyer').count():
        god_ua = UserAccount.get(UserAccount.username=='god')
        GameObject.create_scripted_object(
            god_ua, 'god/foyer', 'room',
            {'name': 'Foyer',
             'description': "A waiting room. Magazines in every language from every decade litter dusty end tables sitting between overstuffed armchairs." })

def reset_db():
    get_db().drop_tables(MODELS)
    init_db()
