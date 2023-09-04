import os
from contextlib import contextmanager
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv


load_dotenv()
database_uri = os.environ['DATABASE_URI']

pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=database_uri)

@contextmanager
def get_connection():
    connection = pool.getconn()
    try:
        yield connection
    finally:
        pool.putconn(connection)