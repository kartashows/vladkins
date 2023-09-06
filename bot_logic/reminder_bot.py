import os
import logging
from datetime import datetime
import re

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot_logic.utils import (default_keyboard,
                             get_select_medicines_keyboard,
                             get_location_button,
                             get_timezone,
                             get_utc_hours_minutes_date)
import bot_logic.utils as utils
from db.database import (add_user,
                         add_medicine,
                         add_medicine_job,
                         add_intake,
                         list_all_medicines,
                         delete_medicine,
                         get_user_timezone,
                         get_medicine_jobs,
                         get_interval_job,
                         delete_interval_job)
from db.connection_pool import get_connection


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.environ['TOKEN']

reminder_bot = Bot(token=TOKEN)
dp = Dispatcher(reminder_bot, storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=os.environ['SYSTEM_TIMEZONE'])
if scheduler.running:
    scheduler.shutdown()
else:
    scheduler.start()


class Setup(StatesGroup):
    Location = State()


class Add(StatesGroup):
    AddMedicineName = State()
    AddMedicineDailyIntakeTimes = State()
    AddMedicineTime = State()


class Delete(StatesGroup):
    DeleteMedicine = State()


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(utils.WELCOME_MESSAGE, reply_markup=get_location_button())
    await Setup.Location.set()


@dp.message_handler(content_types=[types.ContentType.LOCATION, types.ContentType.TEXT], state=Setup.Location)
async def create_user_execute(message: types.Message, state: FSMContext):
    if message.location is None:
        await message.reply(utils.USER_INPUT_LOCATION_CHECK, reply_markup=get_location_button())
        await Setup.Location.set()
        return
    user_id = message.from_user.id
    timezone = get_timezone(longitude=message.location.longitude, latitude=message.location.latitude)
    with get_connection() as connection:
        add_user(connection, user_id, timezone)
        await message.answer(utils.TIMEZONE_SUCCESS.format(timezone),
                             reply_markup=default_keyboard,
                             parse_mode=types.ParseMode.MARKDOWN)
        await state.finish()


@dp.message_handler(lambda message: message.text == utils.default_add_button)
async def add_medicine_prompt(message: types.Message):
    await message.answer(utils.MEDICINE_NAME_PROMPT)
    await Add.AddMedicineName.set()


@dp.message_handler(state=Add.AddMedicineName)
async def add_medicine_name_prompt(message: types.Message, state: FSMContext):
    medicine_name = message.text
    async with state.proxy() as medicine_data:
        medicine_data['name'] = medicine_name
    await message.answer(utils.MEDICINE_INTAKE_TIMES_PROMPT)
    await Add.AddMedicineDailyIntakeTimes.set()


@dp.message_handler(state=Add.AddMedicineDailyIntakeTimes)
async def add_medicine_daily_intake_prompt(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or (int(message.text) < 1 or int(message.text) > 10):
        await message.answer(utils.USER_INPUT_DAILY_INTAKES_CHECK)
        await Add.AddMedicineDailyIntakeTimes.set()
        return
    times = int(message.text)
    async with state.proxy() as medicine_data:
        medicine_data['times'] = times
        medicine_data['times_prompt_counter'] = times
        medicine_data['scheduled_time'] = []
        await message.answer(utils.MEDICINE_SCHEDULED_TIME_PROMPT)
        await Add.AddMedicineTime.set()


@dp.message_handler(state=Add.AddMedicineTime)
async def add_medicine_time_prompt_and_execute(message: types.Message, state: FSMContext):
    if not bool(re.match(r'^\d\d:\d\d$', message.text)):
        await message.reply(utils.USER_INPUT_SCHEDULE_TIME_CHECK)
        await Add.AddMedicineTime.set()
        return
    async with state.proxy() as medicine_data:
        medicine_data['scheduled_time'].append(message.text)
        medicine_data['times_prompt_counter'] -= 1
        if medicine_data['times_prompt_counter'] != 0:
            await message.answer(utils.MEDICINE_SCHEDULED_TIME_PROMPT)
        else:
            user_id = message.from_user.id
            with get_connection() as connection:
                insertion_check = add_medicine(connection,
                                               medicine_data['name'],
                                               user_id,
                                               ','.join(medicine_data['scheduled_time']))
                if insertion_check != '':
                    timezone = get_user_timezone(connection, user_id)
                    chat_id = message.chat.id
                    for time in medicine_data['scheduled_time']:
                        hours, minutes, date = get_utc_hours_minutes_date(time, timezone)
                        job = scheduler.add_job(utils.set_reminder_cron,
                                                trigger='cron',
                                                hour=hours,
                                                minute=minutes,
                                                start_date=date,
                                                kwargs={'bot': reminder_bot,
                                                        'chat_id': chat_id,
                                                        'user_id': user_id,
                                                        'medicine_name': medicine_data['name']})
                        logger.info(f"Scheduled {job.id} job for {job.next_run_time}!")
                        add_medicine_job(connection, medicine_data['name'], user_id, job.id)
                    await message.answer(
                        utils.MEDICINE_TOTAL_INFO.format(medicine_data['name'], medicine_data['scheduled_time']),
                        reply_markup=default_keyboard,
                        parse_mode=types.ParseMode.MARKDOWN)
                else:
                    await message.answer(utils.MEDICINE_INSERTION_FAIL.format(medicine_data['name']),
                                         reply_markup=default_keyboard)

            await state.finish()


@dp.message_handler(lambda message: message.text == utils.default_list_button)
async def list_user_medicine_execute(message: types.Message):
    with get_connection() as connection:
        medicines = list_all_medicines(connection, message.from_user.id)
        if not medicines:
            await message.answer(utils.MEDICINE_NAMES_EMPTY, reply_markup=default_keyboard)
        else:
            medicines_scheduled = """"""
            for medicine in medicines:
                medicines_scheduled += utils.MEDICINE_NAME_WITH_SCHEDULE.format(medicine[0], medicine[1])
            await message.answer(medicines_scheduled,
                                 reply_markup=default_keyboard,
                                 parse_mode=types.ParseMode.MARKDOWN)


@dp.message_handler(lambda message: message.text == utils.default_delete_button)
async def delete_user_medicine_prompt(message: types.Message):
    with get_connection() as connection:
        medicines = list_all_medicines(connection, message.from_user.id)
        medicine_names = [medicine[0] for medicine in medicines]
        if not medicine_names:
            await message.answer(utils.MEDICINE_NAMES_EMPTY)
        else:
            await message.answer(text=utils.MEDICINE_NAME_DELETE_PROMPT,
                                 reply_markup=get_select_medicines_keyboard(medicine_names))
            await Delete.DeleteMedicine.set()


@dp.message_handler(state=Delete.DeleteMedicine)
async def delete_user_medicine_execute(message: types.Message, state: FSMContext):
    medicine_name = message.text
    user_id = str(message.from_user.id)
    with get_connection() as connection:
        job_ids = get_medicine_jobs(connection, medicine_name, user_id)
        for job_id in job_ids:
            scheduler.remove_job(job_id)
        delete_medicine(connection, medicine_name, user_id)
        await message.answer(utils.MEDICINE_DELETE_SUCCESS.format(medicine_name), reply_markup=default_keyboard)
        await state.finish()


@dp.callback_query_handler(lambda query: query.data.startswith('button'))
async def process_reminder_callback_buttons(query: types.CallbackQuery):
    button_pressed = query.data
    if 'done' in button_pressed:
        status = 'done'
        response = utils.CALLBACK_RESPONSE_DONE
    else:
        status = 'skipped'
        response = utils.CALLBACK_RESPONSE_SKIPPED
    with get_connection() as connection:
        user_id, medicine_name = button_pressed.split('_')[-2:]
        date = datetime.now().strftime("%H:%M %Y-%m-%d")
        add_intake(connection, medicine_name, user_id, date, status=status)
        job_id = get_interval_job(connection, medicine_name, user_id)
        scheduler.remove_job(str(job_id[0]))
        delete_interval_job(connection, medicine_name, user_id)
        await query.answer(response)
    await reminder_bot.edit_message_reply_markup(chat_id=query.message.chat.id,
                                                 message_id=query.message.message_id,
                                                 reply_markup=None)
    await reminder_bot.edit_message_text(
        chat_id=query.message.chat.id,
        message_id=query.message.message_id,
        text=utils.REMINDER_TEXT_UPDATE.format(medicine_name),
    )
