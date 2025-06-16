import asyncio
import os
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.filters import Command  # ✅ v3 filter 写法

from lz_config import API_TOKEN, BOT_MODE, WEBHOOK_PATH, WEBHOOK_HOST,AES_KEY
from lz_db import db

from handlers import lz_media_parser, lz_search_highlighted
from handlers import lz_menu

import lz_var

import aiogram
print(f"✅ aiogram version: {aiogram.__version__}")

lz_var.start_time = time.time()
lz_var.cold_start_flag = True

async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    print(f"🔗 設定 Telegram webhook 為：{webhook_url}")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url)
    
    
    lz_var.cold_start_flag = False  # 启动完成

async def health(request):
    uptime = time.time() - lz_var.start_time
    if lz_var.cold_start_flag or uptime < 10:
        return web.Response(text="⏳ Bot 正在唤醒，请稍候...", status=503)
    return web.Response(text="✅ Bot 正常运行", status=200)

async def main():
    bot = Bot(
        token=API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    
     # ✅ 赋值给 lz_var 让其他模块能引用
    lz_var.bot = bot

    me = await bot.get_me()
    lz_var.bot_username = me.username
    lz_var.bot_id = me.id



       
   


    dp = Dispatcher()
    dp.include_router(lz_search_highlighted.router)
    dp.include_router(lz_media_parser.router)  # ✅ 注册你的新功能模块
    dp.include_router(lz_menu.router)

    await db.connect()

    # ✅ Telegram /ping 指令（aiogram v3 正确写法）
    @dp.message(Command(commands=["ping", "status"]))
    async def check_status(message: types.Message):
        uptime = int(time.time() - lz_var.start_time)
        await message.reply(f"✅ Bot 已运行 {uptime} 秒，目前状态良好。")

    if BOT_MODE == "webhook":
        dp.startup.register(on_startup)
        print("🚀 啟動 Webhook 模式")

        app = web.Application()
        app.router.add_get("/", health)  # ✅ 健康检查路由

        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

        # ✅ Render 环境用 PORT，否则本地用 8080
        port = int(os.environ.get("PORT", 8080))
        await web._run_app(app, host="0.0.0.0", port=port)
    else:
        print("🚀 啟動 Polling 模式")
        await db.connect()
        await dp.start_polling(bot, polling_timeout=10.0)

if __name__ == "__main__":
    print("🟡 Cold start in progress...")
    asyncio.run(main())
    print(f"✅ Bot cold started in {int(time.time() - lz_var.start_time)} 秒")
