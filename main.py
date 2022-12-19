#!/usr/bin/env python3
import json
import logging
import traceback
from tempfile import TemporaryDirectory

from mastodon import AttribAccessDict, CallbackStreamListener, Mastodon
from telegram import Bot, InputMediaPhoto, InputMediaVideo, Message, Update
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
    return ''.join(traceback.TracebackException.from_exception(exc).format())


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hi!')


def error(update: Update, context: CallbackContext) -> None:
    logging.warning('Update "%s" caused error "%s"', update, context.error)
    logging.exception(context.error)


def send_message_to_mastodon(update: Update, context: CallbackContext) -> None:
    channel_post = update.channel_post
    if channel_post.chat_id != cfg.channel_chat_id:
        logging.warning(
            f'Received message from wrong channel id: {channel_post.chat_id}')
        channel_post.reply_text(
            "This bot is only for specific channel.")
        return
    logging.info(
        f'Received channel message from channel id: {channel_post.chat_id}')
    try:
        def _get_forward_name() -> str | None:
            if channel_post.forward_from:
                return channel_post.forward_from.full_name
            if channel_post.forward_from_chat:
                return channel_post.forward_from_chat.title
            if channel_post.forward_sender_name:
                return channel_post.forward_sender_name
            return None

        forawrd = _get_forward_name()
        media_ids = None
        text = ''

        if channel_post.photo:
            if channel_post.media_group_id:
                logging.info('This is a media group. Skip it.')
                return
            with TemporaryDirectory(prefix='mastodon') as tmpdir:
                text = channel_post.caption or ''
                if any(tag in text for tag in cfg.noforward_tags):
                    logging.info(
                        'Do not forward this channel message to mastodon.')
                    return
                file_path = f'{tmpdir}/{channel_post.photo[-1].file_unique_id}'
                channel_post.photo[-1].get_file().download(
                    custom_path=file_path)
                media_ids = mastondon.media_post(file_path).id
        elif channel_post.video:
            with TemporaryDirectory(prefix='mastodon') as tmpdir:
                text = channel_post.caption or ''
                if any(tag in text for tag in cfg.noforward_tags):
                    logging.info(
                        'Do not forward this channel message to mastodon.')
                    return
                file_path = f'{tmpdir}/{channel_post.video.file_name}'
                channel_post.video.get_file().download(custom_path=file_path)
                media_ids = mastondon.media_post(file_path).id
        elif channel_post.text:
            text = channel_post.text
            if any(tag in text for tag in cfg.noforward_tags):
                logging.info(
                    'Do not forward this channel message to mastodon.')
                return
            if forawrd:
                text += f'\n\nForwarded from {forawrd}'
            if cfg.add_link_in_mastodon:
                link = f'from: https://t.me/c/{str(channel_post.chat_id)[4:]}/{channel_post.message_id}'
                text += f'\n\n{link}'
        else:
            logging.info(f'Unsupported message type, skip it.')
            return

        if cfg.show_forward_info and forawrd:
            text += f'\n\nForwarded from {forawrd}'
        if cfg.add_link_in_mastodon:
            link = f'from: https://t.me/c/{str(channel_post.chat_id)[4:]}/{channel_post.message_id}'
            text += f'\n\n{link}'
        mastondon.status_post(
            status=text, visibility='public', media_ids=media_ids)
        context.bot.send_message(
            cfg.pm_chat_id, f'Successfully forward message to mastodon.\n{text}')
    except Exception as e:
        logging.exception(e)
        context.bot.send_message(
            cfg.pm_chat_id, f'```{format_exception(e)}```', parse_mode='MarkdownV2')


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
            txt = status.content
            if cfg.add_link_in_telegram:
                txt += f"from: {status.url}"
            logging.info(f'Sending message to telegram channel: {txt}')
            if len(status.media_attachments) > 0:
                medias = []
                for item in status.media_attachments:
                    if item.type == 'image':
                        medias.append(InputMediaPhoto(
                            item.url, parse_mode='HTML'))
                    elif item.type == 'video':
                        medias.append(InputMediaVideo(
                            item.url, parse_mode='HTML'))
                medias[0].caption = txt
                logging.info('Sending media group to telegram channel.')
                bot.send_media_group(cfg.channel_chat_id, medias)
            else:
                logging.info(
                    'Sending pure-text message to telegram channel.')
                bot.send_message(
                    cfg.channel_chat_id, txt, parse_mode='HTML', disable_web_page_preview=True)
    except Exception as e:
        logging.exception(e)
        bot.send_message(
            cfg.pm_chat_id, f'```{format_exception(e)}```', parse_mode='MarkdownV2')


if __name__ == '__main__':
    # Mastodon stream
    listener = CallbackStreamListener(update_handler=send_message_to_telegram)
    mastondon.stream_user(listener=listener, run_async=True)

    # Telegram bot
    updater = Updater(bot=bot, use_context=True)
    dp: Dispatcher = updater.dispatcher
    dp.add_error_handler(error)
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(MessageHandler(
        Filters.update.channel_post, send_message_to_mastodon))
    updater.start_polling()
    updater.idle()
