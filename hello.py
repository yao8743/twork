from asyncio import sleep
import os
from telethon import TelegramClient

# 检查是否在本地开发环境中运行
if not os.getenv('GITHUB_ACTIONS'):
    from dotenv import load_dotenv
    load_dotenv()

# 从环境变量中获取值
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')

# 设置 API ID 和 API Hash

session_name = api_id + 'session_name'  # 确保与上传的会话文件名匹配

# 创建 Telegram 客户端
client = TelegramClient(session_name, api_id, api_hash)

# 机器人或用户 ID 列表
bots = ['botA', 'botB', '4478232']

async def send_messages():
    # 连接到 Telegram
    await client.start()

    # 遍历列表并发送消息
    for bot_id in bots:
        try:
            await client.send_message(bot_id, "/start")
            print(f"Message sent to {bot_id}: /start")
        except Exception as e:
            print(f"Failed to send message to {bot_id}: {e}")
        finally:
            await sleep(0.5)  # 等待 1 秒

# 主入口
if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(send_messages())
