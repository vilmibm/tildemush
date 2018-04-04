import playhouse.migrate as m

from .config import get_db
from .models import MODELS

def initial(db, _):
    db.create_tables(MODELS)

MIGRATIONS = [
    initial,
]

def migrate():
    db = get_db()
    migrator = m.PostgresqlMigrator(db)
    for migration in MIGRATIONS:
        migration(db, migrator)

def reset_db():
    get_db().drop_tables(MODELS)
    migrate()
