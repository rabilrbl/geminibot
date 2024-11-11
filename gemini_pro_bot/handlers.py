import asyncio
from gemini_pro_bot.llm import model, llm_manager
from google.generativeai.types.generation_types import (
    StopCandidateException,
    BlockedPromptException,
)
import google.generativeai as genai
from telegram import Update , InlineKeyboardButton , InlineKeyboardMarkup ,BotCommand
from telegram.ext import (
    ContextTypes,Application
)
from telegram.error import NetworkError, BadRequest
from telegram.constants import ChatAction, ParseMode
from gemini_pro_bot.html_format import format_message
import PIL.Image as load_image
from io import BytesIO
from datetime import datetime
import os


def new_chat(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data["chat"] = model.start_chat()


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}!\n\nStart sending messages with me to generate a response.\n\nSend /new to start a new chat session.",
        # reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
Basic commands:
/start - Start the bot
/help - Get help. Shows this message
/model - Select LLM model to use

Chat commands:
/new - Start a new chat session (model will forget previously generated messages)

Send a message to the bot to generate a response.
"""
    await update.message.reply_text(help_text)


async def newchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new chat session."""
    init_msg = await update.message.reply_text(
        text="Starting new chat session...",
        reply_to_message_id=update.message.message_id,
    )
    new_chat(context)
    await init_msg.edit_text("New chat session started.")


# Define the function that will handle incoming messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages from users.

    Checks if a chat session exists for the user, initializes a new session if not.
    Sends the user's message to the chat session to generate a response.
    Streams the response back to the user, handling any errors.
    """
    if context.chat_data.get("chat") is None:
        new_chat(context)
    text = update.message.text
    init_msg = await update.message.reply_text(
        text="请稍后...", reply_to_message_id=update.message.message_id
    )
    await update.message.chat.send_action(ChatAction.TYPING)
    # Generate a response using the text-generation pipeline
    chat = context.chat_data.get("chat")  # Get the chat session for this chat
    response = None
    try:
        response = await chat.send_message_async(
            text, stream=True
        )  # Generate a response
    except StopCandidateException as sce:
        print("Prompt: ", text, " was stopped. User: ", update.message.from_user)
        print(sce)
        await init_msg.edit_text("The model unexpectedly stopped generating.")
        chat.rewind()  # Rewind the chat session to prevent the bot from getting stuck
        return
    except BlockedPromptException as bpe:
        print("Prompt: ", text, " was blocked. User: ", update.message.from_user)
        print(bpe)
        await init_msg.edit_text("Blocked due to safety concerns.")
        if response:
            # Resolve the response to prevent the chat session from getting stuck
            await response.resolve()
        return
    full_plain_message = ""
    # Stream the responses
    async for chunk in response:
        try:
            if chunk.text:
                full_plain_message += chunk.text
                message = format_message(full_plain_message)
                init_msg = await init_msg.edit_text(
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
        except StopCandidateException as sce:
            await init_msg.edit_text("The model unexpectedly stopped generating.")
            chat.rewind()  # Rewind the chat session to prevent the bot from getting stuck
            continue
        except BadRequest:
            await response.resolve()  # Resolve the response to prevent the chat session from getting stuck
            continue
        except NetworkError:
            raise NetworkError(
                "Looks like you're network is down. Please try again later."
            )
        except IndexError:
            await init_msg.reply_text(
                "Some index error occurred. This response is not supported."
            )
            await response.resolve()
            continue
        except Exception as e:
            print(e)
            if chunk.text:
                full_plain_message = chunk.text
                message = format_message(full_plain_message)
                init_msg = await update.message.reply_text(
                    text=message,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=init_msg.message_id,
                    disable_web_page_preview=True,
                )
        # Sleep for a bit to prevent the bot from getting rate-limited
        await asyncio.sleep(0.1)


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming images with captions and generate a response."""
    init_msg = await update.message.reply_text(
        text="请稍后...",
        reply_to_message_id=update.message.message_id
    )
    try:
        # 获取图片文件
        images = update.message.photo
        if not images:
            await init_msg.edit_text("No image found in the message.")
            return

        # 获取最大尺寸的图片
        image = max(images, key=lambda x: x.file_size)
        file = await image.get_file()

        # 下载图片数据
        image_data = await file.download_as_bytearray()

        # 上传图片到 Gemini
        gemini_file = upload_to_gemini(image_data)

        # 准备文件列表
        files = [gemini_file]

        # 获取提示文本
        prompt = update.message.caption if update.message.caption else "Analyse this image and generate response"
        if context.chat_data.get("chat") is None:
            new_chat(context)
        # 生成响应
        await update.message.chat.send_action(ChatAction.TYPING)
        # Generate a response using the text-generation pipeline
        chat_session = context.chat_data.get("chat")
        chat_session.history.append({
                "role": "user",
                "parts": [
                    files[0],
                ],
            })
        # 使用 Gemini 生成响应
        response = await chat_session.send_message_async(
            prompt,
            stream=True
        )
        # 处理响应
        full_plain_message = ""
        async for chunk in response:
            try:
                if chunk.text:
                    full_plain_message += chunk.text
                    message = format_message(full_plain_message)
                    init_msg = await init_msg.edit_text(
                        text=message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
            except Exception as e:
                print(f"Error in response streaming: {e}")
                if not full_plain_message:
                    await init_msg.edit_text(f"Error generating response: {str(e)}")
                break
            await asyncio.sleep(0.1)

    except Exception as e:
        print(f"Error processing image: {e}")
        await init_msg.edit_text(f"Error processing image: {str(e)}")

def upload_to_gemini(image_data, mime_type="image/png"):
    """Uploads the given image data to Gemini."""
    # 生成临时文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_filename = f"temp_image_{timestamp}.png"

    try:
        # 保存临时文件
        with open(temp_filename, 'wb') as f:
            f.write(image_data)

        # 上传到 Gemini
        file = genai.upload_file(temp_filename, mime_type=mime_type)
        print(f"Uploaded file '{file.display_name}' as: {file.uri}")
        return file
    finally:
        # 删除临时文件
        if os.path.exists(temp_filename):
            os.remove(temp_filename)


async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /model command - show model selection menu."""
    keyboard = []
    models = llm_manager.get_available_models()

    for model_id, model_info in models.items():
        # 为每个模型创建一个按钮
        keyboard.append([InlineKeyboardButton(
            f"{model_info['name']} {'✓' if model_id == llm_manager.current_model else ''}",
            callback_data=f"model_{model_id}"
        )])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "选择要使用的模型:",
        reply_markup=reply_markup
    )

async def model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle model selection callback."""
    query = update.callback_query
    await query.answer()

    # 从callback_data中提取模型ID
    model_id = query.data.replace("model_", "")

    if llm_manager.switch_model(model_id):
        models = llm_manager.get_available_models()
        await query.edit_message_text(
            f"已切换到 {models[model_id]['name']} 模型"
        )
    else:
        await query.edit_message_text("模型切换失败")
