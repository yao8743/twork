import asyncio
import time
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# 定义一个 /start 命令处理函数
async def start(update, context):
    await update.message.reply_text('Hello! 我是你的 Telegram 机器人!')

# 定义一个处理不同类型消息的函数
async def handle_message(update, context):
    message = update.message
    response = "你发送的是未知消息类型。"
    if message.text:
        response = f"你发送的是文本消息: {message.text}"
    await update.message.reply_text(response)

async def polling_with_intervals(application, max_runtime):
    start_time = time.time()  # 记录开始时间
    total_run_time = 0

    while total_run_time < max_runtime:
        print(f"启动轮询, 当前运行时间 {total_run_time} 秒")

        # 启动 90 秒的轮询
        polling_task = asyncio.create_task(application.start_polling())
        await asyncio.sleep(90)

        # 休息 60 秒
        print("休息 60 秒")
        application.stop()  # 停止轮询
        await asyncio.sleep(60)

        # 计算总运行时间
        total_run_time = time.time() - start_time

    print("运行完成，总时长达到 1000 秒，程序结束。")

def main():
    bot_token = os.getenv('BOT_TOKEN')  # 这里你需要加载你的 bot_token
    max_runtime = 1000  # 总执行时长为 1000 秒

    try:
        print("启动机器人...")

        # Application 对象只需创建一次
        application = Application.builder().token(bot_token).build()

        # 注册 /start 命令处理程序
        application.add_handler(CommandHandler("start", start))

        # 注册消息处理程序，处理所有消息类型
        application.add_handler(MessageHandler(filters.ALL, handle_message))

        # 启动轮询循环
        asyncio.run(polling_with_intervals(application, max_runtime))
    except KeyboardInterrupt:
        print("机器人已手动停止")
    finally:
        print("程序结束")

if __name__ == '__main__':
    main()
