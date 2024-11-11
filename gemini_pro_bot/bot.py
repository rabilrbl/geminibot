import os
from telegram import Update, BotCommand
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    Application,
    CallbackQueryHandler,
)
from gemini_pro_bot.filters import AuthFilter, MessageFilter, PhotoFilter
from dotenv import load_dotenv
from gemini_pro_bot.handlers import (
    start,
    help_command,
    newchat_command,
    handle_message,
    handle_image,
    model_command,
    model_callback,
)
import asyncio
import logging

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def setup_commands(application: Application) -> None:
    """设置机器人的命令菜单"""
    commands = [
        BotCommand(command='start', description='开始使用机器人'),
        BotCommand(command='help', description='获取帮助信息'),
        BotCommand(command='new', description='开始新的对话'),
        BotCommand(command='model', description='选择 AI 模型'),
    ]
    # await application.bot.set_my_commands(commands)

def start_bot() -> None:
    """启动机器人"""
    try:
        # 创建应用实例
        application = Application.builder().token(os.getenv("BOT_TOKEN")).build()
        # 添加命令处理器
        application.add_handler(CommandHandler("start", start, filters=AuthFilter))
        application.add_handler(CommandHandler("help", help_command, filters=AuthFilter))
        application.add_handler(CommandHandler("new", newchat_command, filters=AuthFilter))

        # 处理文本消息
        application.add_handler(MessageHandler(MessageFilter, handle_message))

        # 处理图片消息
        application.add_handler(MessageHandler(PhotoFilter, handle_image))

        # 添加模型选择命令
        application.add_handler(CommandHandler("model", model_command, filters=AuthFilter))

        # 添加回调处理器
        application.add_handler(CallbackQueryHandler(model_callback, pattern="^model_"))
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logging.error(f"启动机器人时发生错误: {e}")
        raise
