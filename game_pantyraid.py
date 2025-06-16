import asyncio
import random
import os
import aiomysql
from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.client.default import DefaultBotProperties
from game_panty_template import PANTY_MOVE_TEMPLATES, SCENE_TEMPLATES,IMAGE_REWARD_MAP

from aiogram import BaseMiddleware
from aiogram.types import Update

import asyncio
import time

# 加载环境变量
if not os.getenv('GITHUB_ACTIONS'):
    from dotenv import load_dotenv
    load_dotenv('.game.env')




API_TOKEN = os.getenv('API_TOKEN')
MYSQL_DB_NAME = os.getenv('MYSQL_DB_NAME')
MYSQL_DB_USER = os.getenv('MYSQL_DB_USER')
MYSQL_DB_PASSWORD = os.getenv('MYSQL_DB_PASSWORD')
MYSQL_DB_HOST = os.getenv('MYSQL_DB_HOST')
MYSQL_DB_PORT = int(os.getenv('MYSQL_DB_PORT', 3306))

bot = Bot(API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

games = {}  # 群组游戏实例



NAME_POOL = ["依依", "小姚", "小胖", "小唯", "球球", "小宇", "童童", "俊伟", "小石头", "飞飞"]
POINT_COST = 25
POINT_REWARD = 50
DEFAULT_POINT = 0


class ThreadSafeThrottleMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 1.0):
        super().__init__()
        self.rate_limit = rate_limit
        self._user_time = {}
        self._lock = asyncio.Lock()

    async def __call__(self, handler, event: Update, data: dict):
        user_id = event.from_user.id if event.from_user else None
        now = time.monotonic()

        if user_id:
            async with self._lock:
                last_time = self._user_time.get(user_id, 0)
                if now - last_time < self.rate_limit:
                    return  # ✅ 直接结束，不继续传递
                self._user_time[user_id] = now

        return await handler(event, data)




# ========== MySQL Manager ==========
class MySQLPointManager:
    def __init__(self, pool):
        self.pool = pool

    @router.message(F.photo)
    async def handle_photo(message: Message):
        # 取最后一张（通常是最高分辨率）
        photo = message.photo[-1]
        file_id = photo.file_id
        await message.answer(f"🖼️ 你发的图片 file_id 是：<code>{file_id}</code>")

    async def get_user_point(self, user_id: int) -> int:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT point FROM user WHERE user_id = %s", (user_id,))
                row = await cur.fetchone()
                return row[0] if row else 0

    async def update_user_point(self, user_id: int, delta: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE user SET point = point + %s WHERE user_id = %s", (delta, user_id))
                await conn.commit()

    async def get_or_create_user(self, user_id: int) -> int:
        point = await self.get_user_point(user_id)
        if point == 0:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("INSERT IGNORE INTO user (user_id, point) VALUES (%s, %s)", (user_id, DEFAULT_POINT))
                    await conn.commit()
            return DEFAULT_POINT
        return point

# ========== 游戏类 ==========
class PantyRaidGame:
    def __init__(self, image_file_id):
        self.image_file_id = image_file_id
        self.reward_file_id = IMAGE_REWARD_MAP.get(image_file_id)
        self.names = random.sample(NAME_POOL, 4)
        self.true_boy = random.choice(self.names)
        self.claimed = {}
        self.finished = False
        self.lock = asyncio.Lock()

    def is_all_claimed(self):
        return len(self.claimed) == 4

    def get_game_description(self):
        return (
            "🎭 <b>脱裤大作战开始！</b>\n\n"
            "四个弟弟排排站，只有一个是小基弟弟！\n\n"
            "快站到你怀疑的弟弟面前，大会会开始播放AV，等一声令下——脱！裤！\n"
            "真相只有一个，看你能不能一眼识破！\n\n"
            f"每次脱裤需要消耗 {POINT_COST} 积分。\n"
            "四个弟弟中，只有一位是看了AV不是 JJ In In De。\n"
            f"猜中可获得 {POINT_REWARD} 积分奖励以及脱裤后的照片！😊\n\n"
            "🩲 请选择你要锁定的目标：(可多选)"
        )

    def get_keyboard(self):
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"🩲 {name}", callback_data=f"panty_{name}")]
                             for name in self.names]
        )

    async def handle_panty(self, callback: CallbackQuery, choice: str):
        async with self.lock:
            user_id = callback.from_user.id
            user_name = callback.from_user.full_name

            if self.finished:
                await safe_callback_answer(callback, "游戏已结束。", True)
                return

            if choice in self.claimed:
                await safe_callback_answer(callback, f"这个弟弟已被 {self.claimed[choice]['user_name']} 预订！", True)
                await callback.message.edit_reply_markup(reply_markup=self.disable_button(callback.message.reply_markup, choice))
                return

            points = await point_manager.get_or_create_user(user_id)
            if points < POINT_COST:
                await safe_callback_answer(callback, "你的积分不够啦！", True)
                return

            await point_manager.update_user_point(user_id, -POINT_COST)
            self.claimed[choice] = {'user_id': user_id, 'user_name': user_name}
            await callback.message.edit_reply_markup(reply_markup=self.disable_button(callback.message.reply_markup, choice))
            await callback.message.answer(random.choice(PANTY_MOVE_TEMPLATES).format(user_name=user_name, choice=choice))

            if self.is_all_claimed():
                await self.reveal_results(callback)

    async def reveal_results(self, callback: CallbackQuery):
        self.finished = True
        winner_uid = None
        summary_lines = [f"🔔 小基弟弟是：<span class='tg-spoiler'>{self.true_boy}</span>\r\n"]

        for name, claimer in self.claimed.items():
            uid = claimer['user_id']
            uname = claimer['user_name']
            if name == self.true_boy:
                winner_uid = uid
                text = random.choice(SCENE_TEMPLATES).format(player=uname, target=name, result=f"小基弟弟，🎉 获得 {POINT_REWARD} 积分！")
                summary_lines.append(f"<span class='tg-spoiler'>{text}</span>")
                await point_manager.update_user_point(uid, POINT_REWARD)


        bot_username = (await bot.get_me()).username
        notice = f"\r\n⚠️ 请赢家先私聊 <a href='https://t.me/{bot_username}'>@{bot_username}</a> 领取奖励！"
        summary_lines.append(notice)

        reply_markup = get_winner_keyboard(winner_uid) if winner_uid else None
        # await callback.message.answer("\n".join(summary_lines), reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        result_msg = await callback.message.answer("\n".join(summary_lines), reply_markup=reply_markup, parse_mode=ParseMode.HTML)

        # 启动领奖超时任务
        if winner_uid:
            asyncio.create_task(self.wait_for_reward_timeout(result_msg))
    # def disable_button(self, keyboard: InlineKeyboardMarkup, choice: str) -> InlineKeyboardMarkup:
    #     return InlineKeyboardMarkup(inline_keyboard=[
    #         [InlineKeyboardButton(text=f"{btn.text}（已被选定）", callback_data="disabled") if btn.callback_data == f"panty_{choice}" else btn for btn in row]
    #         for row in keyboard.inline_keyboard
    #     ])


    async def wait_for_reward_timeout(self, result_msg: Message):
        await asyncio.sleep(15)  # 等待 15 秒
        try:
            # 取出当前按钮的 callback_data
            if result_msg.reply_markup and result_msg.reply_markup.inline_keyboard:
                current_callback_data = result_msg.reply_markup.inline_keyboard[0][0].callback_data
                if current_callback_data and current_callback_data.startswith("reward_"):
                    # 按钮还在领奖状态，替换成再来一局
                    await result_msg.edit_reply_markup(reply_markup=get_restart_keyboard())
        except Exception as e:
            print(f"处理领奖超时失败: {e}")


    def disable_button(self, keyboard: InlineKeyboardMarkup, choice: str) -> InlineKeyboardMarkup:
        new_kb = []
        for row in keyboard.inline_keyboard:
            new_row = []
            for button in row:
                if button.callback_data != f"panty_{choice}":
                    new_row.append(button)  # 只保留未被选中的按钮
            if new_row:
                new_kb.append(new_row)
        return InlineKeyboardMarkup(inline_keyboard=new_kb)


# ========== 通用按钮 ==========
def get_winner_keyboard(winner_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎁 领取脱下裤子的照片", callback_data=f"reward_{winner_id}")]]
    )

def get_restart_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔄 再来一局", callback_data="restart_game")]]
    )

# ========== 防止旧 Query 错误 ==========
async def safe_callback_answer(callback: CallbackQuery, text: str, show_alert: bool = False):
    try:
        await callback.answer(text, show_alert=show_alert)
    except Exception as e:
        print(f"忽略 query 错误: {e}")

# ========== 游戏控制 ==========
@router.message(Command("start_pantyraid"))
async def start_game(message: Message):
    chat_id = message.chat.id
    existing_game = games.get(chat_id)
    if existing_game and not existing_game.finished:
        await message.answer("⚠️ 本局游戏尚未结束，请先完成当前游戏再开启新局！")
        return
    await start_new_game(chat_id, message)

@router.callback_query(F.data.startswith("panty_"))
async def handle_panty(callback: CallbackQuery):



    chat_id = callback.message.chat.id
    game = games.get(chat_id)
    if game:
        await game.handle_panty(callback, callback.data.split("_")[1])
    else:
        await safe_callback_answer(callback, "游戏未开始或已结束。", True)

@router.callback_query(F.data.startswith("reward_"))
async def handle_reward(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = games.get(chat_id)
    if not game:
        await safe_callback_answer(callback, "❌ 本轮游戏不存在或已结束。", True)
        return

    winner_id = int(callback.data.split("_")[1])
    if callback.from_user.id != winner_id:
        await safe_callback_answer(callback, "❌ 你不是赢家，不能领取奖励！", True)
        return

    if not game.reward_file_id:
        await safe_callback_answer(callback, "⚠️ 此轮没有设置奖励图片。", True)
        return

    await bot.send_photo(callback.from_user.id, photo=game.reward_file_id, caption="🎉 这是你的奖励！")
    await safe_callback_answer(callback, "奖励已发送到你的私聊！", True)
    await callback.message.edit_reply_markup(reply_markup=get_restart_keyboard())

@router.callback_query(F.data == "restart_game")
async def handle_restart_game(callback: CallbackQuery):
    # 先暂停3秒，避免重复点击
    await asyncio.sleep(3)


    chat_id = callback.message.chat.id

    # # 替换按钮为“已点击”状态，防止重复点
    # await callback.message.edit_reply_markup(
    #     reply_markup=InlineKeyboardMarkup(
    #         inline_keyboard=[[InlineKeyboardButton(text="✅ 已重新开始", callback_data="disabled")]]
    #     )
    # )


    # 直接删除按钮
    await callback.message.edit_reply_markup(reply_markup=None)

    await start_new_game(chat_id, callback.message)
    await safe_callback_answer(callback, "已开启新一局！")

@router.message(Command("points"))
async def check_points(message: Message):
    points = await point_manager.get_or_create_user(message.from_user.id)
    await message.answer(f"🪙 你目前有 {points} 积分")

# ========== 启动新游戏 ==========
async def start_new_game(chat_id: int, message: Message):
    image_file_id = random.choice(list(IMAGE_REWARD_MAP.keys()))
    game = PantyRaidGame(image_file_id)
    games[chat_id] = game
    await message.answer_photo(photo=image_file_id, caption=game.get_game_description(), reply_markup=game.get_keyboard())

# ========== 数据库连接 ==========
async def init_mysql_pool():
    return await aiomysql.create_pool(
        host=MYSQL_DB_HOST,
        port=MYSQL_DB_PORT,
        user=MYSQL_DB_USER,
        password=MYSQL_DB_PASSWORD,
        db=MYSQL_DB_NAME,
        autocommit=True
    )

# ========== 启动 ==========
async def main():
    global point_manager
    pool = await init_mysql_pool()
    point_manager = MySQLPointManager(pool)

    # 添加限速中间件（2秒限制一次）
    dp.message.middleware(ThreadSafeThrottleMiddleware(rate_limit=2.0))
    dp.callback_query.middleware(ThreadSafeThrottleMiddleware(rate_limit=2.0))

    dp.include_router(router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
