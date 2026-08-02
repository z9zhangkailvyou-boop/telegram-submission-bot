#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Submission Bot - 投稿机器人
Rewritten for python-telegram-bot 20.x
Original: https://github.com/Netrvin/telegram-submission-bot
"""

import json
import os
import logging
import asyncio
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
)
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

Version_Code = 'v2.0.0'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PATH = os.path.dirname(os.path.realpath(__file__)) + '/'

# Load config
with open(PATH + 'config.json', 'r') as f:
    CONFIG = json.load(f)

# Load data
with open(PATH + 'data.json', 'r') as f:
    submission_list = json.load(f)


def save_data():
    with open(PATH + 'data.json', 'w') as f:
        json.dump(submission_list, f, ensure_ascii=False)


def save_config():
    with open(PATH + 'config.json', 'w', encoding='utf-8') as f:
        json.dump(CONFIG, f, indent=4, ensure_ascii=False)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await update.message.reply_text(
        "欢迎使用投稿机器人！\n\n"
        "可接收的投稿类型:\n"
        "• 文字\n"
        "• 图片\n"
        "• 音频/语音\n"
        "• 视频\n"
        "• 文件\n\n"
        "直接发送消息即可投稿。"
    )


async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /version command"""
    await update.message.reply_text(
        f"Telegram Submission Bot\n{Version_Code}\n"
        "https://github.com/Netrvin/telegram-submission-bot"
    )


async def setgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setgroup command - set review group"""
    if update.message.from_user.id != CONFIG['Admin']:
        return
    CONFIG['Group_ID'] = update.message.chat_id
    save_config()
    await update.message.reply_text("✅ 已设置本群为审稿群")


async def anonymous_post(context: ContextTypes.DEFAULT_TYPE, msg, editor, group_id):
    """Post submission anonymously"""
    global submission_list
    key = f"{group_id}:{msg.message_id}"

    if msg.audio:
        r = await context.bot.send_audio(
            chat_id=CONFIG['Publish_Channel_ID'],
            audio=msg.audio.file_id, caption=msg.caption
        )
    elif msg.document:
        r = await context.bot.send_document(
            chat_id=CONFIG['Publish_Channel_ID'],
            document=msg.document.file_id, caption=msg.caption
        )
    elif msg.voice:
        r = await context.bot.send_voice(
            chat_id=CONFIG['Publish_Channel_ID'],
            voice=msg.voice.file_id, caption=msg.caption
        )
    elif msg.video:
        r = await context.bot.send_video(
            chat_id=CONFIG['Publish_Channel_ID'],
            video=msg.video.file_id, caption=msg.caption
        )
    elif msg.photo:
        r = await context.bot.send_photo(
            chat_id=CONFIG['Publish_Channel_ID'],
            photo=msg.photo[-1].file_id, caption=msg.caption
        )
    else:
        r = await context.bot.send_message(
            chat_id=CONFIG['Publish_Channel_ID'],
            text=msg.text or ""
        )

    submission_list[key]['posted'] = True

    sender_name = submission_list[key]['Sender_Name']
    sender_id = submission_list[key]['Sender_ID']
    markup_id = submission_list[key]['Markup_ID']

    await context.bot.edit_message_text(
        text=f"新投稿\n投稿人: [{sender_name}](tg://user?id={sender_id})\n"
             f"来源: 匿名\n审稿人: [{editor.full_name}](tg://user?id={editor.id})\n✅ 已采用",
        chat_id=group_id,
        message_id=markup_id,
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        await context.bot.send_message(
            chat_id=sender_id,
            text="✅ 您的稿件已过审，感谢您对我们的支持！",
            reply_to_message_id=submission_list[key]['Original_MsgID']
        )
    except Exception:
        pass

    save_data()
    return r


async def real_name_post(context: ContextTypes.DEFAULT_TYPE, msg, editor, group_id):
    """Post submission with source"""
    global submission_list
    key = f"{group_id}:{msg.message_id}"

    r = await context.bot.forward_message(
        chat_id=CONFIG['Publish_Channel_ID'],
        from_chat_id=group_id,
        message_id=msg.message_id
    )

    submission_list[key]['posted'] = True

    sender_name = submission_list[key]['Sender_Name']
    sender_id = submission_list[key]['Sender_ID']
    markup_id = submission_list[key]['Markup_ID']

    await context.bot.edit_message_text(
        text=f"新投稿\n投稿人: [{sender_name}](tg://user?id={sender_id})\n"
             f"来源: 保留\n审稿人: [{editor.full_name}](tg://user?id={editor.id})\n✅ 已采用",
        chat_id=group_id,
        message_id=markup_id,
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        await context.bot.send_message(
            chat_id=sender_id,
            text="✅ 您的稿件已过审，感谢您对我们的支持！",
            reply_to_message_id=submission_list[key]['Original_MsgID']
        )
    except Exception:
        pass

    save_data()
    return r


async def process_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    if update.channel_post is not None:
        return
    if update.message is None:
        return

    msg = update.message

    # Message in review group - reply to forwarded submission = comment + approve
    if msg.chat_id == CONFIG['Group_ID'] and msg.reply_to_message is not None:
        reply = msg.reply_to_message
        if reply.from_user and reply.from_user.id == CONFIG.get('ID', 0):
            key = f"{CONFIG['Group_ID']}:{reply.message_id}"
            if key in submission_list and not submission_list[key].get('posted', False):
                if submission_list[key]['type'] == 'real':
                    post = await real_name_post(context, reply, msg.from_user, CONFIG['Group_ID'])
                else:
                    post = await anonymous_post(context, reply, msg.from_user, CONFIG['Group_ID'])
                # Send comment if any
                if msg.text:
                    await context.bot.send_message(
                        chat_id=CONFIG['Publish_Channel_ID'],
                        text=msg.text,
                        reply_to_message_id=post.message_id
                    )
        return

    # Private message = submission
    if msg.from_user.id == msg.chat_id:
        # Determine if we can offer anonymous option
        can_anonymous = True
        # In python-telegram-bot 22.x, forward_from is replaced by forward_origin
        forward_origin = getattr(msg, 'forward_origin', None)
        if forward_origin is not None:
            from telegram import MessageOriginUser, MessageOriginChat, MessageOriginChannel
            if isinstance(forward_origin, (MessageOriginChat, MessageOriginChannel)):
                can_anonymous = False
            elif isinstance(forward_origin, MessageOriginUser):
                if forward_origin.sender_user.id != msg.from_user.id:
                    can_anonymous = False

        # Encode original message_id into callback_data so we can retrieve it later
        mid = msg.message_id
        if can_anonymous:
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("是", callback_data=f'submission_type:real:{mid}'),
                    InlineKeyboardButton("否", callback_data=f'submission_type:anonymous:{mid}')
                ],
                [InlineKeyboardButton("取消投稿", callback_data='cancel:submission')]
            ])
        else:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("是", callback_data=f'submission_type:real:{mid}')],
                [InlineKeyboardButton("取消投稿", callback_data='cancel:submission')]
            ])

        await msg.reply_text(
            "即将完成投稿...\n您是否想要保留消息来源（保留消息发送者用户名）？",
            reply_markup=markup
        )


async def process_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    global submission_list
    query = update.callback_query
    await query.answer()

    # Review group - approve button
    if query.message.chat_id == CONFIG['Group_ID']:
        if query.data == 'receive:real':
            await real_name_post(context, query.message.reply_to_message, query.from_user, CONFIG['Group_ID'])
            return
        if query.data == 'receive:anonymous':
            await anonymous_post(context, query.message.reply_to_message, query.from_user, CONFIG['Group_ID'])
            return
        if query.data in ('reject:real', 'reject:anonymous'):
            # Find the submission in the list
            rejected = None
            for k, v in submission_list.items():
                if v.get('Markup_ID') == query.message.message_id:
                    rejected = v
                    break
            # Notify the user
            if rejected and rejected.get('Sender_ID'):
                try:
                    await context.bot.send_message(
                        chat_id=rejected['Sender_ID'],
                        text="❌ 很抱歉，您的投稿未通过审核。"
                    )
                except Exception:
                    pass
            # Update the review message
            await query.edit_message_text("❌ 已拒绝该投稿")
            # Remove from submission list
            if rejected:
                for k, v in list(submission_list.items()):
                    if v.get('Markup_ID') == query.message.message_id:
                        del submission_list[k]
                        break
                save_data()
            return

    # Cancel submission
    if query.data == 'cancel:submission':
        await query.edit_message_text("已取消投稿")
        return

    # User chose submission type - forward to review group
    if CONFIG['Group_ID'] == 0:
        await query.edit_message_text("❌ 审稿群未设置，请联系管理员")
        return

    # Parse callback_data: 'submission_type:real:msg_id' or 'submission_type:anonymous:msg_id'
    parts = query.data.split(':')
    if len(parts) < 3:
        await query.edit_message_text("❌ 数据错误，请重新投稿")
        return
    sub_type = parts[1]  # 'real' or 'anonymous'
    original_msg_id = int(parts[2])
    sender = query.from_user

    # Forward to review group
    fwd_msg = await context.bot.forward_message(
        chat_id=CONFIG['Group_ID'],
        from_chat_id=query.message.chat_id,
        message_id=original_msg_id
    )

    key = f"{CONFIG['Group_ID']}:{fwd_msg.message_id}"

    submission_list[key] = {
        'posted': False,
        'Sender_Name': sender.full_name,
        'Sender_ID': sender.id,
        'Original_MsgID': original_msg_id,
    }

    msg_text = f"新投稿\n投稿人: [{sender.full_name}](tg://user?id={sender.id})\n来源: "

    if sub_type == 'real':
        msg_text += "保留"
        submission_list[key]['type'] = 'real'
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 采用", callback_data='receive:real'),
                InlineKeyboardButton("❌ 拒绝", callback_data='reject:real')
            ]
        ])
    elif sub_type == 'anonymous':
        msg_text += "匿名"
        submission_list[key]['type'] = 'anonymous'
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 采用", callback_data='receive:anonymous'),
                InlineKeyboardButton("❌ 拒绝", callback_data='reject:anonymous')
            ]
        ])
    else:
        return

    markup_msg = await context.bot.send_message(
        chat_id=CONFIG['Group_ID'],
        text=msg_text,
        reply_to_message_id=fwd_msg.message_id,
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN
    )

    submission_list[key]['Markup_ID'] = markup_msg.message_id

    await query.edit_message_text("✅ 感谢您的投稿，请等待审核")
    save_data()


def main():
    """Start the bot"""
    app = Application.builder().token(CONFIG['Token']).build()

    # Store bot ID in config
    async def post_init(application):
        bot_info = await application.bot.get_me()
        CONFIG['ID'] = bot_info.id
        CONFIG['Username'] = '@' + bot_info.username
        logger.info(f"Bot started: {CONFIG['Username']} (ID: {CONFIG['ID']})")

    app.post_init = post_init

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("version", version_command))
    app.add_handler(CommandHandler("setgroup", setgroup_command))
    app.add_handler(CallbackQueryHandler(process_callback))
    app.add_handler(MessageHandler(
        filters.TEXT | filters.AUDIO | filters.PHOTO |
        filters.VIDEO | filters.VOICE | filters.Document.ALL,
        process_msg
    ))

    logger.info("Starting bot with long polling...")
    app.run_polling(drop_pending_updates=True)
    save_data()
    logger.info("Bot stopped, data saved.")


if __name__ == '__main__':
    main()
