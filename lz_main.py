import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from lz_config import API_TOKEN,BOT_MODE,WEBHOOK_PATH,WEBAPP_HOST,WEBAPP_PORT,WEBHOOK_HOST
from lz_db import db
from handlers import lz_search_highlighted

 


async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
    await bot.delete_webhook(drop_pending_updates=True)  # ✅ 清掉 polling 模式
    await bot.set_webhook(webhook_url)

async def main():

    bot = Bot(
        token=API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

   
    # dp = Dispatcher()
    dp = Dispatcher()
    dp.include_router(lz_search_highlighted.router)
    dp.startup.register(on_startup)
    await db.connect()
   
    

    if BOT_MODE == "webhook":
        print(f"🚀 啟動 Webhook 模式於 http://{WEBAPP_HOST}:{WEBAPP_PORT}{WEBHOOK_PATH}")
        await dp.start_webhook(
            webhook_path=WEBHOOK_PATH,
            host=WEBAPP_HOST,
            port=int(WEBAPP_PORT),
            bot=bot
        )
    else:
        print("🚀 啟動 Polling 模式")
        await dp.start_polling(bot, polling_timeout=10.0)

    

if __name__ == "__main__":
    asyncio.run(main())
