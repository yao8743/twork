import asyncio
import json
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import Command
from news_db import NewsDatabase
from news_config import DB_DSN, API_TOKEN

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
db = NewsDatabase(DB_DSN)

news_buffer = {
    "title": None,
    "text": None,
    "file_id": None,
    "file_type": None,
    "button_str": None,
    "bot_name": None,
    "business_type": None,
    "id": None
}

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("🤖 你好，请直接发送图片、影片或文件，并附上 JSON 格式 caption。")

@dp.message(lambda msg: msg.photo or msg.video or msg.document)
async def receive_media(message: Message):
    caption = message.caption or ""

    try:
        result = json.loads(caption)
    except Exception:
        await message.reply("⚠️ Caption 不是合法的 JSON。")
        return

    if not isinstance(result, dict) or "caption" not in result:
        await message.reply("⚠️ JSON 缺少必要字段 caption。")
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

    # 统一写入 news_buffer
    news_buffer.update({
        "id": result.get("id"),
        "file_id": file_id,
        "file_type": file_type,
        "text": result.get("caption", ""),
        "button_str": result.get("button_str"),
        "title": result.get("title", ""),
        "bot_name": me.username,
        "business_type": result.get("business_type")
    })

    await db.init()

    payload = {k: news_buffer.get(k) for k in ["text", "file_id", "file_type", "button_str", "bot_name", "business_type"]}

    if news_buffer["id"]:
        await db.update_news_by_id(news_id=news_buffer["id"], **payload)
        await message.reply(f"🔁 已更新新闻 ID = {news_buffer['id']}")
    else:
        news_id = await db.insert_news(title=news_buffer["title"] or "Untitled", **payload)
        await db.create_send_tasks(news_id, business_type=news_buffer.get("business_type") or "news")
        await message.reply(f"✅ 已新增新闻并建立任务，新闻 ID = {news_id}")

async def periodic_sender():
    from news_sender import send_news_batch
    while True:
        await send_news_batch()
        await asyncio.sleep(10)

async def main():
    await db.init()
    loop = asyncio.get_event_loop()
    loop.create_task(periodic_sender())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
