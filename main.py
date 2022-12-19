#!/usr/bin/env python3
import json
import logging
import traceback
from pprint import pformat
from tempfile import TemporaryDirectory

from markdownify import markdownify
from mastodon import AttribAccessDict, CallbackStreamListener, Mastodon
from telegram import Bot, InputMediaPhoto, InputMediaVideo, Update
from telegram.ext import (CallbackContext, CommandHandler, Dispatcher, Filters,
                          MessageHandler, Updater)

with open('config.json', 'r') as f:
    cfg = json.load(f, object_hook=AttribAccessDict)

logging.basicConfig(level=cfg.log_level,
                    format='%(asctime)s %(levelname)s %(message)s',
                    handlers=[logging.StreamHandler()])
mastondon = Mastodon(access_token=cfg.mastodon_api_access_token,
                     api_base_url=cfg.mastodon_host)
bot = Bot(token=cfg.tg_bot_token)


def format_exception(exc: Exception) -> str:
    return ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hi!')


def error(update: Update, context: CallbackContext) -> None:
    logging.warning('Update "%s" caused error "%s"', update, context.error)
    print(context.error)


def send_message_to_mastodon(update: Update, context: CallbackContext) -> None:
    message = update.channel_post or update.message
    if message.chat_id != cfg.channel_chat_id:
        logging.warning(
            f'Received message from wrong channel id: {message.chat_id}')
        message.reply_text(
            "This bot is only for specific channel.")
        return
    logging.info(
        f'Received channel message from channel id: {message.chat_id}')
    try:
        forawrd = None
        media_ids = None
        text = ''

        if message.forward_from:
            forawrd = message.forward_from.full_name
        elif message.forward_from_chat:
            forawrd = message.forward_from_chat.title
        elif message.forward_sender_name:
            forawrd = message.forward_sender_name

        if message.photo:
            if message.media_group_id:
                logging.info('This is a media group. Skip it.')
                return
            with TemporaryDirectory(prefix='mastodon') as tmpdir:
                text = message.caption or ''
                if any(tag in text for tag in cfg.noforward_tags):
                    logging.info(
                        'Do not forward this channel message to mastodon.')
                    return
                file_path = f'{tmpdir}/{message.photo[-1].file_unique_id}'
                message.photo[-1].get_file().download(
                    custom_path=file_path)
                media_ids = mastondon.media_post(file_path).id
        elif message.video:
            with TemporaryDirectory(prefix='mastodon') as tmpdir:
                text = message.caption or ''
                if any(tag in text for tag in cfg.noforward_tags):
                    logging.info(
                        'Do not forward this channel message to mastodon.')
                    return
                file_path = f'{tmpdir}/{message.video.file_name}'
                message.video.get_file().download(custom_path=file_path)
                media_ids = mastondon.media_post(file_path).id
        elif message.text:
            text = message.text
            if any(tag in text for tag in cfg.noforward_tags):
                logging.info(
                    'Do not forward this channel message to mastodon.')
                return
            if cfg.show_forward_info and forawrd:
                text += f'\n\nForwarded from {forawrd}'
            if cfg.add_link_in_mastodon:
                link = f'from: https://t.me/c/{str(message.chat_id)[4:]}/{message.message_id}'
                text += f'\n\n{link}'
        else:
            logging.info(f'Unsupported message type, skip it.')
            return

        if cfg.show_forward_info and forawrd:
            text += f'\n\nForwarded from {forawrd}'
        if cfg.add_link_in_mastodon:
            link = f'from: https://t.me/c/{str(message.chat_id)[4:]}/{message.message_id}'
            text += f'\n\n{link}'
        mastondon.status_post(
            status=text, visibility='public', media_ids=media_ids)
        context.bot.send_message(
            cfg.pm_chat_id, f'Successfully forward message to mastodon.\n{text}')
    except Exception as e:
        logging.exception(e)
        context.bot.send_message(
            cfg.pm_chat_id, f'```{format_exception(e)}```', parse_mode='Markdown')


def send_message_to_telegram(status: AttribAccessDict) -> None:
    def is_valid(status: AttribAccessDict) -> bool:
        # check if the message is from the telegram channel or another app
        return status.account.username == cfg.mastodon_username and \
            (status.application is None or status.application.name != cfg.mastodon_app_name) and \
            status.in_reply_to_id is None and \
            status.visibility in cfg.scope
    try:
        if is_valid(status):
            logging.info(f'Forwarding message from mastodon to telegram.')
            if status.reblog:
                # check if it is a reblog
                # get the original message
                status = status.reblog
            txt = markdownify(status.content)
            if cfg.add_link_in_telegram:
                txt += f"from: {status.url}"
            logging.info(f'Sending message to telegram channel: {txt}')
            if len(status.media_attachments) > 0:
                medias = []
                for item in status.media_attachments:
                    if item.type == 'image':
                        medias.append(InputMediaPhoto(
                            item.url, parse_mode='Markdown'))
                    elif item.type == 'video':
                        medias.append(InputMediaVideo(
                            item.url, parse_mode='Markdown'))
                medias[0].caption = txt
                logging.info('Sending media group to telegram channel.')
                bot.send_media_group(cfg.channel_chat_id, medias)
            else:
                logging.info(
                    'Sending pure-text message to telegram channel.')
                bot.send_message(
                    cfg.channel_chat_id, txt, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception as e:
        logging.exception(e)
        bot.send_message(
            cfg.pm_chat_id, f'```{format_exception(e)}```', parse_mode='Markdown')


if __name__ == '__main__':
    # Mastodon stream
    listener = CallbackStreamListener(update_handler=send_message_to_telegram)
    mastondon.stream_user(listener=listener, run_async=True)

    # Telegram bot
    updater = Updater(bot=bot, use_context=True)
    dp: Dispatcher = updater.dispatcher
    dp.add_error_handler(error)
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(~Filters.command, send_message_to_mastodon))
    updater.start_polling()
    updater.idle()
