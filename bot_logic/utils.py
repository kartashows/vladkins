from typing import List
from datetime import datetime, timedelta

from aiogram.types import (InlineKeyboardMarkup,
                           InlineKeyboardButton,
                           ReplyKeyboardMarkup,
                           KeyboardButton)
from aiogram import Bot
from timezonefinder import TimezoneFinder
import pytz

from db.connection_pool import get_connection
from db.database import add_interval_job, get_user_intakes, db_empty, get_rows, clear_table, add_medicine_job, get_user, get_user_timezone


# buttons
DEFAULT_ADD_BUTTON = "Добавить лекарство"
DEFAULT_LIST_BUTTON = "Показать мои лекарства"
DEFAULT_DELETE_BUTTON = "Удалить лекарство"
DEFAULT_SEE_INTAKES_BUTTON = "Моя история лекарств"

# emojis
waving_hand = '\U0001F44B'
doctor = '\U0001F468'
savouring_face = '\U0001F60B'
globe = '\U0001F30D'
party_face = '\U0001F973'

# texts
WELCOME_MESSAGE = f"""Привет! {waving_hand}\n
Меня зовут доктор Владкинс. {doctor}\n
Для начала давай определимся с твоим часовым поясом {globe}\n
Вместо твоей клавиатуры сейчас появилась кнопка "Поделиться часовым поясом" - нажми её!"""
USER_ALREADY_EXISTS = f"Ты уже есть в моей базе! {party_face}"
TIMEZONE_SUCCESS = "Отлично! Ваш часовой пояс - *{}*."
MEDICINE_NAME_PROMPT = "Пожалуйста, введи название лекарства."
MEDICINE_NAME_MULTIPLE_BUTTON_PRESS = 'Достаточно один раз нажать на кнопку! Введи название препарата.'
MEDICINE_INTAKE_TIMES_PROMPT = "Сколько раз в день?"
MEDICINE_SCHEDULED_TIME_PROMPT = "Пожалуйста, введи время в формате 00:00."
MEDICINE_TOTAL_INFO = "Добавил *{}* в базу и поставил на время: *{}*."
MEDICINE_INSERTION_FAIL = "Препарат {} уже добавлен."
MEDICINE_INSERTION_SUCCESS = "Препарат {} успешно добавлен!"
MEDICINE_NAME_DELETE_PROMPT = "Введи название препарата, который ты хочешь удалить."
MEDICINE_DELETE_SUCCESS = "Препарат {} успешно удален."
MEDICINE_DELETE_CANCEL = "Удаление отменено."
MEDICINE_NAMES_EMPTY = "Пока ещё ничего не добавлено."
MEDICINE_NAME_WITH_SCHEDULE = "*{}* со следующим расписанием: *{}*\n"
CALLBACK_RESPONSE_DONE = "Записано успешно!"
CALLBACK_RESPONSE_SKIPPED = "Пропущенно успешно!"
REMINDER_TEXT = "Время принимать {}! {}"
REMINDER_TEXT_UPDATE = "{} {}!"
USER_INPUT_STATELESS = 'Пожалуйста, используй предложенные команды: \
"Добавить", "Показать мои лекарства" или "Удалить лекарство"'
USER_INPUT_LOCATION_CHECK = "Пожалуйста, отправь мне свой часовой пояс, нажав на предложенную кнопку."
USER_INPUT_MEDICINE_NAME_CHECK = "{} не похоже на название лекарства...\n Отправь ещё раз полное название!"
USER_INPUT_DAILY_INTAKES_CHECK = "Пожалуста, введи число от 1 до 10."
USER_INPUT_SCHEDULE_TIME_CHECK = "Пожалуйста, введи время в формате 00:00."


def get_remind_keyboard(user_id: str, medicine_name: str) -> InlineKeyboardMarkup:
    done = InlineKeyboardButton("Done!", callback_data=f'button_done_{user_id}_{medicine_name}')
    skip = InlineKeyboardButton("Skip!", callback_data=f'button_skip_{user_id}_{medicine_name}')
    remind_keyboard = InlineKeyboardMarkup().add(done, skip)
    return remind_keyboard


def get_default_keyboard():
    default_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    default_keyboard.row(DEFAULT_ADD_BUTTON)
    default_keyboard.row(DEFAULT_LIST_BUTTON, DEFAULT_DELETE_BUTTON, DEFAULT_SEE_INTAKES_BUTTON)
    return default_keyboard


# tz
def get_location_button():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    location_button = KeyboardButton(text="Поделиться часовым поясом", request_location=True)
    keyboard.add(location_button)
    return keyboard


def get_timezone(longitude, latitude) -> str:
    tz_finder = TimezoneFinder()
    timezone = tz_finder.timezone_at(lng=longitude, lat=latitude)
    if not timezone:
        return "Not Found"
    return timezone


# other keyboards
def get_select_medicines_keyboard(medicines: List[str]):
    select_medicines_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    medicine_buttons = [InlineKeyboardButton(medicine, callback_data=f'select_{medicine}') for medicine in medicines]
    select_medicines_keyboard.add(*medicine_buttons)
    return select_medicines_keyboard


def convert_timezone_to_utc_offset(timezone_name):
    target_timezone = pytz.timezone(timezone_name)
    utc_time = datetime.now()
    offset_difference = target_timezone.utcoffset(utc_time)
    utc_offset = timedelta(seconds=offset_difference.total_seconds())
    return utc_offset


def get_utc_hours_minutes_date(time: str, timezone: str):
    input_time = datetime.strptime(time, '%H:%M')
    utc_time = input_time - convert_timezone_to_utc_offset(timezone)
    return utc_time.hour, utc_time.minute, utc_time.now()


def set_reminder_cron(bot: Bot, chat_id: int, medicine_name: str, user_id: str):
    from bot_logic.reminder_bot import scheduler
    job = scheduler.add_job(send_reminder,
                            trigger='interval',
                            seconds=900,
                            next_run_time=datetime.now(),
                            kwargs={'bot': bot,
                                    'chat_id': chat_id,
                                    'user_id': user_id,
                                    'medicine_name': medicine_name})
    with get_connection() as connection:
        add_interval_job(connection, medicine_name, user_id, job.id)


async def send_reminder(bot: Bot, chat_id: int, medicine_name: str, user_id: str):
    text = REMINDER_TEXT.format(medicine_name, savouring_face)
    await bot.send_message(chat_id, text, reply_markup=get_remind_keyboard(user_id, medicine_name))


def get_intake_history_csv(user_id: str):
    with get_connection() as connection:
        return get_user_intakes(connection, user_id)


def check_user_exists(connection, user_id: str) -> bool:
    return len(get_user(connection, user_id)) > 0


def resume_scheduled_jobs(connection, bot: Bot, logger):
    # if jobs table not empty -> clear the table -> rescheduler all jobs and add to the jobs table
    from bot_logic.reminder_bot import scheduler

    if db_empty(connection, "jobs"):
        logger.info("No jobs to resume!")
        return 1
    clear_table(connection, "jobs")
    medicines = get_rows(connection, 'medicines')
    for medicine in medicines:
        medicine_name = medicine[1]
        user_id = medicine[2]
        chat_id = medicine[3]
        schedule = medicine[4].split(',')
        timezone = get_user_timezone(connection, user_id)
        for time in schedule:
            hours, minutes, date = get_utc_hours_minutes_date(time, timezone)
            job = scheduler.add_job(set_reminder_cron,
                                    trigger='cron',
                                    hour=hours,
                                    minute=minutes,
                                    start_date=date,
                                    kwargs={'bot': bot,
                                            'chat_id': chat_id,
                                            'user_id': user_id,
                                            'medicine_name': medicine_name})
            logger.info(f"Scheduled {job.id} job for {job.next_run_time}!")
            add_medicine_job(connection, medicine_name, user_id, job.id)
