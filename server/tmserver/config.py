from peewee import PostgresqlDatabase

DB_HOST = 'localhost'
DB_PORT = 5432
DB_UN = 'tildemush'
DB_PW = 'tildemush'
DB_NAME = 'tildemush'

def get_db():
    return PostgresqlDatabase(
        DB_NAME,
        user=DB_UN,
        password=DB_PW,
        host=DB_HOST,
        port=DB_PORT)
