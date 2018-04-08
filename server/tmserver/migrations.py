import peewee as pw
import playhouse.migrate as m

from .config import get_db
from .models import MODELS, User, Log

def initial(db, _):
    db.create_tables([User])

def add_logging(db, _):
    db.create_tables([Log])

def logging_env_column(db, migrator):
    m.migrate(
        migrator.add_column('log', 'env', pw.CharField(null=True))
    )

def logging_remove_actor_column(db, migrator):
    m.migrate(
        migrator.drop_column('log', 'actor_id'))

MIGRATIONS = [
    initial,
    add_logging,
    logging_env_column,
    logging_remove_actor_column
]

def migrate(migrations=MIGRATIONS):
    db = get_db()
    migrator = m.PostgresqlMigrator(db)
    for migration in migrations:
        migration(db, migrator)

def reset_db():
    get_db().drop_tables(MODELS)
    migrate()
