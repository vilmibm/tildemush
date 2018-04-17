import peewee as pw
import playhouse.migrate as m

from .config import get_db
from .models import MODELS, User, Log

def logging_env_column(db, migrator):
    m.migrate(
        migrator.add_column('log', 'env', pw.CharField(null=True))
    )

def logging_remove_actor_column(db, migrator):
    m.migrate(
        migrator.drop_column('log', 'actor_id'))

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

def reset_db():
    get_db().drop_tables(MODELS)
    get_db().create_tables(MODELS)
