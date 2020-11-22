from os import environ

from playhouse.postgres_ext import PostgresqlExtDatabase

DB_HOST = environ.get('PGHOST', 'localhost')
DB_PORT = environ.get('PGPORT', 5432)
DB_UN = environ.get('PGUSER', 'tildemush')
DB_PW = environ.get('PGPASSWORD', 'tildemush')
DB_NAME = environ.get('PGDATABASE', 'tildemush')
TEST_DB_NAME = DB_NAME + '_test'

env = environ.get('TILDEMUSH_ENV', 'live')

def get_db():
    db = None

    if env == 'test':
        db = PostgresqlExtDatabase(
            TEST_DB_NAME,
            user=DB_UN,
            password=DB_PW,
            host=DB_HOST,
            port=DB_PORT)
    else:
        db = PostgresqlExtDatabase(
            DB_NAME,
            user=DB_UN,
            password=DB_PW,
            host=DB_HOST,
            port=DB_PORT)

    return db
