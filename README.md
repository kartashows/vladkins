# Simple Reminder Bot

This telegram bot reminds you of takings pills according to the shedule you specify.

The bot has 4 buttons:
1. Add medicine
2. Delete medicine
3. List all medicine
4. My history (not yet developed)

**Debug**
In main.py there's a debug section which deletes all the tables after the bot is stopped (Ctrl + C). Simply comment out this section to go live.

**Run**
Main configs are set in .env file:
1. Register your bot in @BotFather in tg to get the token.
2. Create a Postgres db instance to set the uri
3. Simply timezone of your machine

Run **python main.py**
