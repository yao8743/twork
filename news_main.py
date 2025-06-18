import asyncio
import os
import json
from aiohttp import web
import aiohttp  # ✅ 这行是关键，解决你的错误
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.filters import CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiojobs.aiohttp import setup as setup_aiojobs, spawn
from aiojobs.aiohttp import get_scheduler_from_app
from news_db import NewsDatabase

from news_config import BOT_TOKEN, DB_DSN, AES_KEY, BOT_MODE, WEBHOOK_PATH, WEBHOOK_HOST

import time

from utils.aes_crypto import AESCrypto
from utils.base62_converter import Base62Converter

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
db = NewsDatabase(DB_DSN)

news_buffer = {
    "content_id": None,
    "title": None,
    "text": None,
    "file_id": None,
    "file_type": None,
    "button_str": None,
    "bot_name": None,
    "business_type": None,
    "id": None
}

lz_var_start_time = time.time()
lz_var_cold_start_flag = True

crypto = AESCrypto(AES_KEY)

def parse_button_str(button_str: str) -> InlineKeyboardMarkup:
    """
    解析格式为：
    按钮1 - http://t.me/Sssvip && 按钮2 - http://t.me/Sssvip
    按钮3 - http://t.me/Sssvip
    """
    if not button_str:
        return None

    keyboard = []
    lines = button_str.strip().split("\n")
    for line in lines:
        buttons = []
        parts = line.split("&&")
        for part in parts:
            part = part.strip()
            if " - " in part:
                text, url = part.split(" - ", 1)
                buttons.append(InlineKeyboardButton(text=text.strip(), url=url.strip()))
        if buttons:
            keyboard.append(buttons)

    if keyboard:
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    return None


@dp.message(Command("start"))
async def start_handler(message: Message, command: CommandObject):
    args = command.args

    if args and args.startswith("s_"):
        encrypted = args[2:]

        try:
            decrypted = crypto.aes_decode(encrypted)
            parts = decrypted.split(";")
            if len(parts) != 3 :
                raise ValueError("格式不正确")

            business_type = {
                "yz": "stone",
                "sl": "salai"
            }.get(parts[0], "unknown")
            # 解析订阅链接


            expire_ts = Base62Converter.base62_to_decimal(parts[1])
            user_id = Base62Converter.base62_to_decimal(parts[2])
            expire_ts = int(expire_ts) + 1735689600

            if expire_ts < time.time():
                await message.answer("⚠️ 此订阅链接已过期。")
                return

            await db.init()
            await db.pool.execute("""
                INSERT INTO news_user (user_id, business_type, expire_at)
                VALUES ($1, $2, to_timestamp($3))
                ON CONFLICT (user_id, business_type)
                DO UPDATE SET expire_at = to_timestamp($3)
            """, user_id, business_type, expire_ts)

            
####

            # 立即找最新一则新闻（business_type = 'stone'）
            latest_news = await db.pool.fetchrow("""
                SELECT id FROM news_content
                WHERE business_type = $1
                ORDER BY id DESC
                LIMIT 1
            """,business_type)

            if latest_news:
                await db.pool.execute("""
                    INSERT INTO news_send_queue (user_ref_id, news_id)
                    SELECT id, $1 FROM news_user
                    WHERE user_id = $2 AND business_type = $3
                    ON CONFLICT DO NOTHING
                """, latest_news["id"], user_id, business_type)


            
            await message.answer("✅ 你已成功订阅！\r\n📅 有效期至："
                                f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expire_ts))}。")

###




        except Exception as e:
            await message.answer(f"⚠️ 链接解析失败：{str(e)}")
    else:
        await message.answer("🤖 哥哥您好，我是鲁仔")


@dp.message(Command("show"))
async def show_news_handler(message: Message, command: CommandObject):
    try:
        news_id = int(command.args.strip())
    except (ValueError, AttributeError):
        await message.reply("⚠️ 请输入正确的新闻 ID，例如 /show 1")
        return

    await db.init()
    record = await db.pool.fetchrow("""
        SELECT file_id, text, file_type, button_str
        FROM news_content
        WHERE id = $1
    """, news_id)

    if not record:
        await message.reply("⚠️ 未找到指定 ID 的新闻")
        return

    keyboard = parse_button_str(record["button_str"])

    if record["file_type"] == "photo" and record["file_id"]:
        await message.bot.send_photo(
            chat_id=message.chat.id,
            photo=record["file_id"],
            caption=record["text"],
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    else:
        await message.reply("⚠️ 该新闻没有有效的照片或不支持的媒体类型")

@dp.message(Command("push"))
async def push_news_handler(message: Message, command: CommandObject):
    try:
        news_id = int(command.args.strip())
    except (ValueError, AttributeError):
        await message.reply("⚠️ 请输入正确的新闻 ID，例如 /push 1")
        return

    await db.init()
    record = await db.pool.fetchrow("""
        SELECT business_type FROM news_content WHERE id = $1
    """, news_id)

    if not record:
        await message.reply("⚠️ 未找到指定 ID 的新闻")
        return

    business_type = record["business_type"] or "news"

    await db.create_send_tasks(news_id, business_type)
    await message.reply(f"✅ 已将新闻 ID = {news_id} 加入 {business_type} 业务类型的推送任务队列")



@dp.message(lambda msg: msg.photo or msg.video or msg.document)
async def receive_media(message: Message):
    caption = message.caption or ""

    try:
        result = json.loads(caption)
    except Exception:
        # await message.reply("⚠️ Caption 不是合法的 JSON。")
        return

    if not isinstance(result, dict) or "caption" not in result:
        # await message.reply("⚠️ JSON 缺少必要字段 caption。")
        return

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"
    else:
        return

    me = await message.bot.get_me()

    content_id_raw = result.get("content_id")
    try:
        content_id = int(content_id_raw) if content_id_raw is not None else None
    except (ValueError, TypeError):
        await message.reply("⚠️ content_id 不是合法的数字或缺失")
        return

    # 统一写入 news_buffer
    business_type = result.get("business_type", "news")
    news_buffer.update({
        "id": result.get("id"),
        "content_id": content_id,
        "file_id": file_id,
        "file_type": file_type,
        "text": result.get("caption", ""),
        "button_str": result.get("button_str"),
        "title": result.get("title", ""),
        "bot_name": me.username,
        "business_type": result.get("business_type")
    })

    await db.init()

    payload = {k: news_buffer.get(k) for k in ["content_id","text", "file_id", "file_type", "button_str", "bot_name", "business_type"]}

    # 先查询是否存在 content_id + bot_name
    existing_news_id = await db.pool.fetchval(
        "SELECT id FROM news_content WHERE content_id = $1 AND bot_name = $2 LIMIT 1",
        news_buffer["content_id"],
        news_buffer["bot_name"]
    )

    if existing_news_id:
        await db.update_news_by_id(news_id=existing_news_id, **payload)
        await message.reply(f"🔁 已更新新闻 ID = {existing_news_id}")
        await db.create_send_tasks(existing_news_id, business_type)
    else:
        news_id = await db.insert_news(title=news_buffer["title"] or "Untitled", **payload)
        await message.reply(f"✅ 已新增新闻并建立任务，新闻 ID = {news_id}")
        await db.create_send_tasks(news_id, business_type)

async def periodic_sender():
    from news_sender import send_news_batch
    while True:
        await send_news_batch()
        await asyncio.sleep(10)

async def on_startup(bot: Bot):
    lz_var_cold_start_flag = False  # 启动完成
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{WEBHOOK_HOST}{WEBHOOK_PATH}")
    
    

async def health(request):
    uptime = time.time() - lz_var_start_time
    if lz_var_cold_start_flag or uptime < 10:
        return web.Response(text="⏳ Bot 正在唤醒，请稍候...", status=503)
    return web.Response(text="✅ Bot 正常运行", status=200)

async def on_shutdown(app):
    await bot.session.close()


async def keep_alive_ping():
    url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if BOT_MODE == "webhook" else f"{WEBHOOK_HOST}/"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    print(f"🌐 Keep-alive ping {url} status {resp.status}")
        except Exception as e:
            print(f"⚠️ Keep-alive ping failed: {e}")
        await asyncio.sleep(300)  # 每 5 分鐘 ping 一次

async def main():
    await db.init()
    if BOT_MODE == "webhook":
        dp.startup.register(on_startup)
        app = web.Application()
        app.router.add_get("/", health)

        # ✅ 初始化 aiojobs（必须在 on_startup 注册前调用）
        setup_aiojobs(app)

        # ✅ 设置 aiogram webhook
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

        # ✅ 用 spawn(app, coro) 启动任务
        async def on_app_start(app):
            await get_scheduler_from_app(app).spawn(periodic_sender())

        task_keep_alive = asyncio.create_task(keep_alive_ping())

        app.on_startup.append(on_app_start)
        app.on_shutdown.append(on_shutdown)

        port = int(os.environ.get("PORT", 8080))
        await web._run_app(app, host="0.0.0.0", port=port)
    else:
        loop = asyncio.get_event_loop()
        loop.create_task(periodic_sender())
        await dp.start_polling(
            bot,
            skip_updates=True,
            timeout=60,
            relax=3.0
        )





if __name__ == "__main__":
    asyncio.run(main())
