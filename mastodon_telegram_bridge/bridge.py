from tempfile import TemporaryDirectory
from typing import Dict, List, Optional

from mastodon import AttribAccessDict, CallbackStreamListener, Mastodon
from telegram import Bot, InputMediaPhoto, InputMediaVideo, ParseMode, Update
from telegram.ext import CallbackContext, CommandHandler, Dispatcher, Filters, MessageHandler, Updater

from mastodon_telegram_bridge import BridgeOptions, MastodonToTelegramOptions, TelegramToMastodonOptions, logger
from mastodon_telegram_bridge.utils import MastodonFooter, TelegramFooter, format_exception, markdownify

ValueType = str | int | bool | List[str]
OptionType = Dict[str, ValueType]


class Bridge:
    def __init__(self, *,
                 telegram: Dict[str, str],
                 mastodon: Dict[str, str],
                 options: Dict[str, OptionType] | Dict[str, BridgeOptions]) -> None:
        if isinstance(options, BridgeOptions):
            self.mastodon_to_telegram = options['mastodon_to_telegram']
            self.telegram_to_mastodon = options['telegram_to_mastodon']
        else:
            self.mastodon_to_telegram = MastodonToTelegramOptions(**options['mastodon_to_telegram'])
            self.telegram_to_mastodon = TelegramToMastodonOptions(**options['telegram_to_mastodon'])

        logger.info('mastodon_to_telegram: %s ', self.mastodon_to_telegram)
        logger.info('telegram_to_mastodon: %s ', self.telegram_to_mastodon)
        # check if the tags start with #
        for tags in (self.telegram_to_mastodon.include,
                     self.telegram_to_mastodon.exclude,
                     self.mastodon_to_telegram.tags):
            if any(not tag.startswith('#') for tag in tags):
                raise ValueError('Tags must start with #')

        # check if both telegram_to_mastodon and mastodon_to_telegram are disabled
        if self.telegram_to_mastodon.disable and self.mastodon_to_telegram.disable:
            raise ValueError('Both telegram_to_mastodon and mastodon_to_telegram are disabled, nothing to do.')

        if self.telegram_to_mastodon.include and self.telegram_to_mastodon.exclude:
            logger.warning('Both include and exclude in telegram_to_mastodon tag filter are set, exclude will be ignored')

        self.mastodon_footer = MastodonFooter(self.telegram_to_mastodon)
        self.telegram_footer = TelegramFooter(self.mastodon_to_telegram)

        self.mastodon = Mastodon(access_token=mastodon['access_token'],
                                 api_base_url=mastodon['api_base_url'])
        self.bot = Bot(token=telegram['bot_token'])

        self.mastodon_username: str = self.mastodon.account_verify_credentials().username
        self.mastodon_app_name: str = self.mastodon.app_verify_credentials().name
        logger.info('Username: %s, App name: %s', self.mastodon_username, self.mastodon_app_name)

    def _should_forward_to_mastodon(self, msg: str) -> bool:
        if include := self.telegram_to_mastodon.include:
            return any(tag in msg for tag in include)
        return not any(tag in msg for tag in self.telegram_to_mastodon.exclude)

    def _should_forward_to_telegram(self, status: AttribAccessDict) -> bool:
        # check if the message is from the telegram channel or another app
        return status.account.username == self.mastodon_username and \
            (status.application is None or status.application.name != self.mastodon_app_name) and \
            status.in_reply_to_id is None and \
            status.visibility in self.mastodon_to_telegram.scope

    def _send_message_to_mastodon(self, update: Update, context: CallbackContext) -> None:
        channel_post = update.channel_post
        cfg = self.telegram_to_mastodon
        if channel_post.chat_id != cfg.channel_chat_id:
            logger.warning('Received message from wrong channel id: %d', channel_post.chat_id)
            channel_post.reply_text('This bot is only for specific channel.')
            return
        logger.info('Received channel message from channel id: %d', channel_post.chat_id)
        try:
            media_ids = None
            text = ''

            if channel_post.photo:
                if channel_post.media_group_id:
                    # TODO: support media group
                    logger.info('This is a media group. Skip it.')
                    return
                with TemporaryDirectory(prefix='mastodon') as tmpdir:
                    text = channel_post.caption or ''
                    if not self._should_forward_to_mastodon(text):
                        logger.info('Do not forward this channel message to mastodon.')
                        return
                    file_path = f'{tmpdir}/{channel_post.photo[-1].file_unique_id}'
                    channel_post.photo[-1].get_file().download(custom_path=file_path)
                    media_ids = self.mastodon.media_post(file_path).id
            elif channel_post.video:
                with TemporaryDirectory(prefix='mastodon') as tmpdir:
                    text = channel_post.caption or ''
                    if not self._should_forward_to_mastodon(text):
                        logger.info('Do not forward this channel message to mastodon.')
                        return
                    file_path = f'{tmpdir}/{channel_post.video.file_name}'
                    channel_post.video.get_file().download(custom_path=file_path)
                    media_ids = self.mastodon.media_post(file_path).id
            elif channel_post.text:
                text = channel_post.text
                if not self._should_forward_to_mastodon(text):
                    logger.info('Do not forward this channel message to mastodon.')
                    return
            else:
                logger.info('Unsupported message type, skip it.')
                return
            text += '\n' + self.mastodon_footer(channel_post)
            status: AttribAccessDict = self.mastodon.status_post(status=text, visibility='public', media_ids=media_ids)
            context.bot.send_message(
                cfg.pm_chat_id, f'*Successfully forward message to mastodon.*\n{status.url}', parse_mode=ParseMode.MARKDOWN)
        except Exception as exc:
            logger.exception(exc)
            context.bot.send_message(cfg.pm_chat_id, f'```{format_exception(exc)}```', parse_mode=ParseMode.MARKDOWN)

    def _send_message_to_telegram(self, status: AttribAccessDict) -> None:
        cfg = self.mastodon_to_telegram
        try:
            if self._should_forward_to_telegram(status):
                logger.info('Forwarding message from mastodon to telegram.')
                if status.reblog:
                    # check if it is a reblog and get the original message
                    if cfg.forward_reblog_link_only:
                        text = self.telegram_footer(status.reblog)
                        logger.info('Sending message to telegram channel: %s', text)
                        self.bot.send_message(cfg.channel_chat_id, text, parse_mode=ParseMode.MARKDOWN)
                        return
                    status = status.reblog
                text = markdownify(status.content)
                if status.spoiler_text:
                    text = f'*{status.spoiler_text}*\n\n{text}'
                text += '\n' + self.telegram_footer(status)
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
                    self.bot.send_media_group(cfg.channel_chat_id, medias)
                else:
                    logger.info('Sending pure-text message to telegram channel.')
                    self.bot.send_message(cfg.channel_chat_id, text,
                                          parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        except Exception as exc:
            logger.exception(exc)
            self.bot.send_message(cfg.pm_chat_id, f'```{format_exception(exc)}```', parse_mode=ParseMode.MARKDOWN)

    def _start(self, update: Update, context: CallbackContext) -> None:
        update.message.reply_text('Hi!')

    def _error(self, update: Update, context: CallbackContext) -> None:
        logger.warning('Update "%s" caused error "%s"', update, context.error)
        logger.exception(context.error)

    def run(self) -> None:
        # Mastodon stream
        if not self.mastodon_to_telegram.disable:
            listener = CallbackStreamListener(update_handler=self._send_message_to_telegram)
            self.mastodon.stream_user(listener=listener, run_async=True)
        else:
            logger.warning('Skip mastodon stream, because mastodon to telegram is disabled.')

        # Telegram bot
        updater = Updater(bot=self.bot, use_context=True)
        dispatcher: Dispatcher = updater.dispatcher
        dispatcher.add_error_handler(self._error)
        dispatcher.add_handler(CommandHandler('start', self._start))
        if not self.telegram_to_mastodon.disable:
            dispatcher.add_handler(MessageHandler(Filters.update.channel_post, self._send_message_to_mastodon))
        else:
            logger.warning('Skip telegram message handler, because telegram to mastodon is disabled.')
        updater.start_polling()
        updater.idle()
