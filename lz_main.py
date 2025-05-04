import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from lz_config import API_TOKEN,BOT_MODE,WEBHOOK_PATH,WEBAPP_HOST,WEBAPP_PORT,WEBHOOK_HOST
from lz_db import db
from handlers import lz_search_highlighted

async def on_startup(bot: Bot):
    await bot.set_webhook(f"{WEBHOOK_HOST}{WEBHOOK_PATH}")

async def main():

    bot = Bot(
        token=API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        request_timeout=10.0  # 原本是 10 秒，可降至 3~5 秒
    )

   
    # dp = Dispatcher()
    dp = Dispatcher()
    dp.include_router(lz_search_highlighted.router)
    await db.connect()
   

    if BOT_MODE == "webhook":
        await dp.start_webhook(
            bot,
            webhook_path=WEBHOOK_PATH,
            on_startup=on_startup,
            host=WEBAPP_HOST,
            port=WEBAPP_PORT
        )
    else:
        await dp.start_polling(bot, polling_timeout=10.0)

    

if __name__ == "__main__":
    asyncio.run(main())
