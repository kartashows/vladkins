import logging
import os
from dotenv import load_dotenv

from aiogram.utils import executor

from bot_logic.reminder_bot import dp, reminder_bot
from bot_logic.utils import resume_scheduled_jobs
from db.connection_pool import get_connection
import db.database as database


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
debug = os.environ['DEBUG']


def main():
    try:
        logger.info("Connecting to the db...")
        with get_connection() as connection:
            logger.info("No errors while connecting to the db!")
            database.create_tables(connection)
            resume_scheduled_jobs(connection, reminder_bot, logger)
        logger.info("Starting Vladking bot...")
        executor.start_polling(dp, skip_updates=True)
    finally:
        # debug mode
        if debug == 'True':
            with get_connection() as connection:
                logger.info("Deleting tables!")
                database.delete_tables(connection)
        logger.info("Stopping Vladkins bot...")


if __name__ == '__main__':
    main()
