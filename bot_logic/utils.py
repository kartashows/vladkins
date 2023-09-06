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
from db.database import add_interval_job


# emojis
waving_hand = '\U0001F44B'
doctor = '\U0001F468'
savouring_face = '\U0001F60B'
globe = '\U0001F30D'

WELCOME_MESSAGE = f"""Привет! {waving_hand}\n
Меня зовут доктор Владкинс. {doctor}\n
Для начала давай определимся с твоим часовым поясом {globe}\n
Вместо твоей клавиатуры сейчас появилась кнопка "Поделиться часовым поясом" - нажми её!"""
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
REMINDER_TEXT_UPDATE = "{} принято!"
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


# default menu
default_add_button = "Добавить"
default_list_button = "Показать мои лекарства"
default_delete_button = "Удалить лекарство"
default_see_intakes_button = "Моя история лекарств"
default_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
default_keyboard.row(default_add_button)
default_keyboard.row(default_list_button, default_delete_button, default_see_intakes_button)


# for timezone selection
select_tz_keyboard = ReplyKeyboardMarkup(row_width=1)
timezone_buttons = [InlineKeyboardButton(text=f'Timezone {i}') for i in range(20)]
select_tz_keyboard.add(*timezone_buttons)


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
