import asyncio
import os
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from lz_config import API_TOKEN, BOT_MODE, WEBHOOK_PATH, WEBHOOK_HOST, WEBAPP_HOST, WEBAPP_PORT
from lz_db import db
from handlers import lz_search_highlighted

import aiogram
print(f"✅ aiogram version: {aiogram.__version__}")

start_time = time.time()
cold_start_flag = True  # 冷启动标志

async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    global cold_start_flag
    cold_start_flag = False  # 启动完成，解除冷启动

async def health(request):
    uptime = time.time() - start_time
    if cold_start_flag or uptime < 10:
        return web.Response(text="⏳ Bot 正在唤醒，请稍候...", status=503)
    return web.Response(text="✅ Bot 正常运行", status=200)


async def main():
    bot = Bot(
        token=API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()
    dp.include_router(lz_search_highlighted.router)
    dp.startup.register(on_startup)
    await db.connect()

    # 新增：Telegram /ping 指令
    @dp.message(commands=["ping", "status"])
    async def check_status(message: types.Message):
        uptime = int(time.time() - start_time)
        await message.reply(f"✅ Bot 已运行 {uptime} 秒，目前状态良好。")


    if BOT_MODE == "webhook":
        print(f"🚀 啟動 Webhook 模式於 http://{WEBAPP_HOST}:{WEBAPP_PORT}{WEBHOOK_PATH}")

        app = web.Application()

        # 掛載 webhook handler
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

        # 健康检查路由
        app.router.add_get("/", health)

        # 啟動 aiohttp server
        await web._run_app(app, host=WEBAPP_HOST, port=int(WEBAPP_PORT))
    else:
        print("🚀 啟動 Polling 模式")
        await dp.start_polling(bot, polling_timeout=10.0)

if __name__ == "__main__":
    asyncio.run(main())
    print(f"✅ Bot cold started in {int(time.time() - start_time)} 秒")