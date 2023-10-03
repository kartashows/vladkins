from typing import List, Tuple

from contextlib import contextmanager
from psycopg2.extensions import AsIs

CREATE_USERS_TABLE = """CREATE TABLE IF NOT EXISTS users
(id SERIAL PRIMARY KEY,
user_tg_id TEXT UNIQUE,
timezone TEXT);"""
CREATE_MEDICINES_TABLE = """CREATE TABLE IF NOT EXISTS medicines 
(id SERIAL PRIMARY KEY,
medicine_name TEXT,
user_id TEXT,
chat_id TEXT,
schedule TEXT,
FOREIGN KEY(user_id) REFERENCES users(user_tg_id),
UNIQUE(medicine_name, user_id));"""
CREATE_JOBS_TABLE = """CREATE TABLE IF NOT EXISTS jobs
(
id SERIAL PRIMARY KEY,
medicine_name TEXT,
user_id TEXT,
job_id TEXT
);"""
CREATE_INTERVAL_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS interval_jobs
(
id SERIAL PRIMARY KEY,
medicine_name TEXT,
user_id TEXT,
job_id TEXT
);"""
CREATE_INTAKES_TABLE = """CREATE TABLE IF NOT EXISTS intakes
(
id SERIAL PRIMARY KEY,
user_id TEXT,
medicine_name TEXT,
date TEXT,
status TEXT
);"""

ADD_USER = "INSERT INTO users (user_tg_id, timezone) VALUES(%s, %s) ON CONFLICT (user_tg_id) DO NOTHING;"
ADD_MEDICINE = """INSERT INTO medicines (medicine_name, user_id, chat_id, schedule)
VALUES(%s, %s, %s, %s)
ON CONFLICT (medicine_name, user_id) DO NOTHING
RETURNING medicine_name;"""
ADD_JOB = """INSERT INTO jobs (medicine_name, user_id, job_id) VALUES(%s, %s, %s);"""
ADD_INTERVAL_JOB = """INSERT INTO interval_jobs (medicine_name, user_id, job_id) VALUES(%s, %s, %s);"""
ADD_INTAKE = """INSERT INTO intakes (user_id, medicine_name, date, status) VALUES(%s, %s, %s, %s);"""

GET_JOB_IDS = """SELECT jobs.job_id FROM jobs WHERE medicine_name = %s AND user_id = %s;"""
GET_INTERVAL_JOB_ID = """SELECT interval_jobs.job_id FROM interval_jobs WHERE medicine_name = %s AND user_id = %s;"""
GET_TIMEZONE = """SELECT users.timezone FROM users WHERE user_tg_id = %s::TEXT;"""
GET_USER_INTAKES = """SELECT medicine_name, date, status FROM intakes WHERE user_id = %s::TEXT;"""
GET_USER = "SELECT * FROM users WHERE user_tg_id = %s::TEXT;"

LIST_ALL_MEDICINE = """SELECT medicine_name, schedule FROM medicines where user_id = %s::TEXT;"""

DELETE_MEDICINE = """DELETE FROM medicines WHERE medicine_name = %s AND user_id = %s::TEXT;"""
DELETE_MEDICINE_JOBS = """DELETE FROM jobs WHERE medicine_name = %s AND user_id = %s::TEXT;"""
DELETE_INTERVAL_JOB = """DELETE FROM interval_jobs WHERE medicine_name = %s AND user_id = %s::TEXT;"""

COUNT_ENTRIES = """SELECT COUNT(*) FROM %s;"""
GET_TABLE_ROWS = """SELECT * FROM %s;"""
CLEAR_TABLE = """DELETE FROM %s;"""


@contextmanager
def get_cursor(connection):
    with connection:
        with connection.cursor() as cursor:
            yield cursor


def create_tables(connection):
    with get_cursor(connection) as cursor:
        cursor.execute(CREATE_USERS_TABLE)
        cursor.execute(CREATE_MEDICINES_TABLE)
        cursor.execute(CREATE_JOBS_TABLE)
        cursor.execute(CREATE_INTERVAL_JOBS_TABLE)
        cursor.execute(CREATE_INTAKES_TABLE)


def add_user(connection, user_id: str,  timezone: str = 'NA'):
    with get_cursor(connection) as cursor:
        cursor.execute(ADD_USER, (user_id, timezone))


def add_medicine(connection, medicine_name: str, user_id: str, chat_id: str, schedule: str) -> str:
    with get_cursor(connection) as cursor:
        cursor.execute(ADD_MEDICINE, (medicine_name, user_id, chat_id, schedule))
        result = cursor.fetchone()
        if result is not None:
            return result[0]
        else:
            return ''


def add_medicine_job(connection, medicine_name: str, user_id: str, job_id: str):
    with get_cursor(connection) as cursor:
        cursor.execute(ADD_JOB, (medicine_name, user_id, job_id))


def add_interval_job(connection, medicine_name: str, user_id: str, job_id: str):
    with get_cursor(connection) as cursor:
        cursor.execute(ADD_INTERVAL_JOB, (medicine_name, user_id, job_id))


def add_intake(connection, medicine_name: str, user_id: str, date: str, status: str):
    with get_cursor(connection) as cursor:
        cursor.execute(ADD_INTAKE, (medicine_name, user_id, date, status))


def list_all_medicines(connection, user_id: str) -> List[Tuple[str, str]]:
    with get_cursor(connection) as cursor:
        cursor.execute(LIST_ALL_MEDICINE, (user_id,))
        return [(medicine[0], medicine[1]) for medicine in cursor.fetchall()]


def delete_medicine(connection, medicine_name: str, user_id: str):
    with get_cursor(connection) as cursor:
        cursor.execute(DELETE_MEDICINE, (medicine_name, user_id))
        cursor.execute(DELETE_MEDICINE_JOBS, (medicine_name, user_id))


def delete_tables(connection):
    with get_cursor(connection) as cursor:
        cursor.execute('DROP TABLE medicines;')
        cursor.execute('DROP TABLE users;')
        cursor.execute('DROP TABLE jobs;')
        cursor.execute('DROP TABLE intakes;')
        cursor.execute('DROP TABLE interval_jobs;')


def get_user_timezone(connection, user_id) -> str:
    with get_cursor(connection) as cursor:
        cursor.execute(GET_TIMEZONE, (user_id,))
        return [row[0] for row in cursor.fetchall()][0]


def get_medicine_jobs(connection, medicine_name: str, user_id: str) -> List[str]:
    with get_cursor(connection) as cursor:
        cursor.execute(GET_JOB_IDS, (medicine_name, user_id))
        return [row[0] for row in cursor.fetchall()]


def get_interval_job(connection, medicine_name: str, user_id: str) -> str:
    with get_cursor(connection) as cursor:
        cursor.execute(GET_INTERVAL_JOB_ID, (medicine_name, user_id))
        job_id = cursor.fetchall()
        return job_id[0]


def delete_interval_job(connection, medicine_name: str, user_id: str):
    with get_cursor(connection) as cursor:
        cursor.execute(DELETE_INTERVAL_JOB, (medicine_name, user_id))


def get_user_intakes(connection, user_id: str):
    with get_cursor(connection) as cursor:
        cursor.execute(GET_USER_INTAKES, (user_id,))
        return cursor.fetchall()


def db_empty(connection, db: str) -> bool:
    with get_cursor(connection) as cursor:
        cursor.execute(COUNT_ENTRIES, (AsIs(db),))
        count = cursor.fetchone()[0]
        return count == 0


def get_rows(connection, db: str) -> List[Tuple]:
    with get_cursor(connection) as cursor:
        cursor.execute(GET_TABLE_ROWS, (AsIs(db),))
        return cursor.fetchall()


def get_user(connection, user_id: str) -> List[Tuple]:
    with get_cursor(connection) as cursor:
        cursor.execute(GET_USER, (user_id,))
        return cursor.fetchall()


def clear_table(connection, db: str):
    with get_cursor(connection) as cursor:
        cursor.execute(CLEAR_TABLE, (AsIs(db),))
