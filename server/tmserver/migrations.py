import peewee as pw
import playhouse.migrate as m

from .config import get_db
from .models import MODELS, GameObject, UserAccount, Contains
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

def bust_ghosts():
    """This function clears out all player objects placed in the world via the
    Contains table. It's intended use is on server startup to clear out
    orphaned player objects left behind by a crash."""
    logger = logging.getLogger('tmserver')
    # In case of crash, we want to clear any player object ghosts so players
    # can reconnect.
    logger.info('looking for ghosts')
    to_clear = []
    for contains in Contains.select():
        if contains.inner_obj.is_player_obj:
            to_clear.append(contains.id)

    if to_clear:
        logger.info('going to clear ghosts: {}'.format(to_clear))
        Contains.delete().where(Contains.id.in_(to_clear)).execute()

def init_db():
    logger = logging.getLogger('tmserver')
    get_db().create_tables(MODELS, safe=True)
    logger.info("db tables: {}".format(get_db().get_tables()))

    if 0 == UserAccount.select().where(UserAccount.username=='god').count():
        logger.info('creating god user accout')
        UserAccount.create(
           username='god',
           password='TODO',  # TODO set from config
           is_god=True)

    if 0 == GameObject.select().where(GameObject.shortname=='god/foyer').count():
        logger.info('creating foyer')
        god_ua = UserAccount.get(UserAccount.username=='god')
        GameObject.create_scripted_object(
            god_ua, 'god/foyer', 'room',
            {'name': 'Foyer',
             'description': "A waiting room. Magazines in every language from every decade litter dusty end tables sitting between overstuffed armchairs." })

    bust_ghosts()


def reset_db():
    get_db().drop_tables(MODELS)
    init_db()
