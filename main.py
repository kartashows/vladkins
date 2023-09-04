import logging

from aiogram.utils import executor

from bot_logic.bot import dp
from db.connection_pool import get_connection
import db.database as database


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    try:
        logger.info("Connecting to the db...")
        with get_connection() as connection:
            logger.info("No errors while connecting to the db!")
            database.create_tables(connection)
        logger.info("Starting Vladking bot...")
        executor.start_polling(dp, skip_updates=True)
    finally:
        #debug mode
        with get_connection() as connection:
            logger.info("Deleting tables!")
            database.delete_tables(connection)
        logger.info("Stopping Vladkins bot...")

if __name__ == '__main__':
    main()