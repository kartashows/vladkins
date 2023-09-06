from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher import FSMContext

import bot_logic.reminder_bot
import bot_logic.utils



class UserInputMiddleware(BaseMiddleware):
    valid_commands = ["Добавить", "Показать мои лекарства", "Удалить лекарство", "/start"]

    async def on_pre_process_message(self, message: types.Message, data: dict):
        state = data.get('state')
        if state:
            if state == reminder_bot.Setup.Location:
                # Check user input for the 'awaiting_name' state
                if not message.text or not message.text.strip():
                    await message.reply("Please provide a valid name.")
                    return
        else:
            if message.text not in self.valid_commands:
                await message.reply(utils.USER_INPUT_STATELESS)

        return
