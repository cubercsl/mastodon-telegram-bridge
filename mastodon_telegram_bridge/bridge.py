from tempfile import TemporaryDirectory
from typing import List

from mastodon import AttribAccessDict, CallbackStreamListener, Mastodon
from telegram import (Bot, InputMediaPhoto, InputMediaVideo,
                      ParseMode, Update)
from telegram.ext import (CallbackContext, CommandHandler, Dispatcher, Filters,
                          MessageHandler, Updater)

from mastodon_telegram_bridge import format_exception, logger, markdownify, MastodonFooter, TelegramFooter


class Bridge:
    def __init__(self, *,
                 tg_bot_token: str,
                 channel_chat_id: int,
                 pm_chat_id: int,
                 mastodon_host: str,
                 mastodon_api_access_token: str,
                 mastodon_app_name: str,
                 mastodon_username: str,
                 scope: List[str],
                 add_link_in_telegram: bool,
                 add_link_in_mastodon: bool,
                 show_forward_info: bool,
                 noforward_tags: List[str]) -> None:
        self.mastodon = Mastodon(access_token=mastodon_api_access_token,
                                 api_base_url=mastodon_host)
        self.bot = Bot(token=tg_bot_token)

        self.mastodon_footer = MastodonFooter(add_link_in_mastodon=add_link_in_mastodon,
                                              show_forward_info=show_forward_info)
        self.telegram_footer = TelegramFooter(add_link_in_telegram=add_link_in_telegram)

        # get the username of the mastodon account
        self.mastodon_username = self.mastodon.account_verify_credentials().username
        if mastodon_username is not None and mastodon_username != self.mastodon_username:
            logger.warning('The username in the config file (%s) does not match the username of the mastodon account (%s).',
                           mastodon_username, self.mastodon_username)
        self.mastodon_app_name = mastodon_app_name
        logger.info('Username: %s, App name: %s', self.mastodon_username, self.mastodon_app_name)

        self.cfg = AttribAccessDict(
            # get the chat id of the telegram channel and error reporting chat
            channel_chat_id=channel_chat_id,
            pm_chat_id=pm_chat_id,
            # filter out the messages that should not be forwarded
            scope=scope,
            noforward_tags=noforward_tags,
        )

    def _should_forward_to_telegram(self, status: AttribAccessDict) -> bool:
        # check if the message is from the telegram channel or another app
        return status.account.username == self.mastodon_username and \
            (status.application is None or status.application.name != self.mastodon_app_name) and \
            status.in_reply_to_id is None and \
            status.visibility in self.cfg.scope

    def _send_message_to_mastodon(self, update: Update, context: CallbackContext) -> None:
        channel_post = update.channel_post
        if channel_post.chat_id != self.cfg.channel_chat_id:
            logger.warning('Received message from wrong channel id: %d', channel_post.chat_id)
            channel_post.reply_text('This bot is only for specific channel.')
            return
        logger.info('Received channel message from channel id: %d', channel_post.chat_id)
        try:
            media_ids = None
            text = ''

            if channel_post.photo:
                if channel_post.media_group_id:
                    logger.info('This is a media group. Skip it.')
                    return
                with TemporaryDirectory(prefix='mastodon') as tmpdir:
                    text = channel_post.caption or ''
                    if any(tag in text for tag in self.cfg.noforward_tags):
                        logger.info('Do not forward this channel message to mastodon.')
                        return
                    file_path = f'{tmpdir}/{channel_post.photo[-1].file_unique_id}'
                    channel_post.photo[-1].get_file().download(custom_path=file_path)
                    media_ids = self.mastodon.media_post(file_path).id
            elif channel_post.video:
                with TemporaryDirectory(prefix='mastodon') as tmpdir:
                    text = channel_post.caption or ''
                    if any(tag in text for tag in self.cfg.noforward_tags):
                        logger.info('Do not forward this channel message to mastodon.')
                        return
                    file_path = f'{tmpdir}/{channel_post.video.file_name}'
                    channel_post.video.get_file().download(custom_path=file_path)
                    media_ids = self.mastodon.media_post(file_path).id
            elif channel_post.text:
                text = channel_post.text
                if any(tag in text for tag in self.cfg.noforward_tags):
                    logger.info('Do not forward this channel message to mastodon.')
                    return
            else:
                logger.info('Unsupported message type, skip it.')
                return
            text += self.mastodon_footer(channel_post)
            self.mastodon.status_post(status=text, visibility='public', media_ids=media_ids)
            context.bot.send_message(self.cfg.pm_chat_id, f'Successfully forward message to mastodon.\n{text}')
        except Exception as exc:
            logger.exception(exc)
            context.bot.send_message(self.cfg.pm_chat_id, f'```{format_exception(exc)}```', parse_mode=ParseMode.MARKDOWN)

    def _send_message_to_telegram(self, status: AttribAccessDict) -> None:
        try:
            if self._should_forward_to_telegram(status):
                logger.info('Forwarding message from mastodon to telegram.')
                if status.reblog:
                    # check if it is a reblog
                    # get the original message
                    status = status.reblog
                text = markdownify(status.content)
                if status.spoiler_text:
                    text = f'*{status.spoiler_text}*\n\n{text}'
                text += self.telegram_footer(status)
                logger.info('Sending message to telegram channel: %s', text)
                if len(status.media_attachments) > 0:
                    medias = []
                    for item in status.media_attachments:
                        if item.type == 'image':
                            medias.append(InputMediaPhoto(item.url, parse_mode=ParseMode.MARKDOWN))
                        elif item.type == 'video':
                            medias.append(InputMediaVideo(item.url, parse_mode=ParseMode.MARKDOWN))
                    medias[0].caption = text
                    logger.info('Sending media group to telegram channel.')
                    self.bot.send_media_group(self.cfg.channel_chat_id, medias)
                else:
                    logger.info('Sending pure-text message to telegram channel.')
                    self.bot.send_message(self.cfg.channel_chat_id, text,
                                          parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        except Exception as exc:
            logger.exception(exc)
            self.bot.send_message(
                self.cfg.pm_chat_id, f'```{format_exception(exc)}```', parse_mode=ParseMode.MARKDOWN)

    def _start(self, update: Update, context: CallbackContext) -> None:
        update.message.reply_text('Hi!')

    def _error(self, update: Update, context: CallbackContext) -> None:
        logger.warning('Update "%s" caused error "%s"', update, context.error)
        logger.exception(context.error)

    def run(self) -> None:
        # Mastodon stream
        listener = CallbackStreamListener(
            update_handler=self._send_message_to_telegram)
        self.mastodon.stream_user(listener=listener, run_async=True)

        # Telegram bot
        updater = Updater(bot=self.bot, use_context=True)
        dispatcher: Dispatcher = updater.dispatcher
        dispatcher.add_error_handler(self._error)
        dispatcher.add_handler(CommandHandler('start', self._start))
        dispatcher.add_handler(MessageHandler(Filters.update.channel_post, self._send_message_to_mastodon))
        updater.start_polling()
        updater.idle()
