from os import environ

from playhouse.postgres_ext import PostgresqlExtDatabase

DB_HOST = 'localhost'
DB_PORT = 5432
DB_UN = 'tildemush'
DB_PW = 'tildemush'
DB_NAME = 'tildemush'
TEST_DB_NAME = 'tildemush_test'

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
