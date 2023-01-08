import asyncio
import logging
import os
from tempfile import TemporaryDirectory
from typing import Type, cast

from mastodon import AttribAccessDict, CallbackStreamListener, Mastodon, MastodonAPIError
from telegram import Bot, InputMediaPhoto, InputMediaVideo, Message, Update, Video
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackContext, CommandHandler, MessageHandler
from telegram.ext.filters import UpdateType
from telegram.helpers import effective_message_type

from .filter import Filter, MastodonFilter, TelegramFilter
from .footer import Footer, MastodonFooter, TelegramFooter
from .typing import (BridgeOptionsDict, MastodonOptionsDict, MastodonToTelegramOptions,
                     MediaGroup, TelegramOptionsDict, TelegramToMastodonOptions)
from .utils import format_exception, markdownify


logger = logging.getLogger(__name__)


class Bridge:
    """The bridge between mastodon and telegram.
    """

    def __init__(self, *,
                 telegram: TelegramOptionsDict,
                 mastodon: MastodonOptionsDict,
                 options: BridgeOptionsDict,
                 mastodon_filter: Type[Filter] = MastodonFilter,
                 telegram_filter: Type[Filter] = TelegramFilter,
                 mastodon_footer: Type[Footer] = MastodonFooter,
                 telegram_footer: Type[Footer] = TelegramFooter) -> None:
        """The bridge between mastodon and telegram.

        Args:
            telegram (TelegramOptionsDict): telegram bot options
            mastodon (MastodonOptionsDict): mastodon client options
            options (BridgeOptionsDict): bridge options. Defaults to None.
            mastodon_filter (Filter, optional): mastodon filter. Defaults to MastodonFilter.
            telegram_filter (Filter, optional): telegram filter. Defaults to TelegramFilter.
            mastodon_footer (Footer, optional): mastodon footer. Defaults to MastodonFooter.
            telegram_footer (Footer, optional): telegram footer. Defaults to TelegramFooter.

        Raises:
            ValueError: options and telegram_to_mastodon_options/mastodon_to_telegram_options are mutually exclusive
            ValueError: options or telegram_to_mastodon_options/mastodon_to_telegram_options must be provided
            ValueError: Both telegram_to_mastodon and mastodon_to_telegram are disabled, nothing to do
        """
        # you can add more arguments in [mastodon] section in config.toml to customize the mastodon client
        self.mastodon = Mastodon(**mastodon)
        # TODO: add more arguments in [telegram] section in config.toml to customize the telegram bot
        self.telegram = Application.builder().token(telegram['token']).pool_timeout(10).build()

        self._mastodon_username: str = self.mastodon.me().username
        self._mastodon_app_name: str = self.mastodon.app_verify_credentials().name

        logger.info('Username: %s, App name: %s', self._mastodon_username, self._mastodon_app_name)

        self.mastodon_to_telegram = MastodonToTelegramOptions(**options['mastodon_to_telegram'])
        self.telegram_to_mastodon = TelegramToMastodonOptions(**options['telegram_to_mastodon'])

        logger.info(self.mastodon_to_telegram)
        logger.info(self.telegram_to_mastodon)

        # check if both telegram_to_mastodon and mastodon_to_telegram are disabled
        if self.telegram_to_mastodon.disable and self.mastodon_to_telegram.disable:
            raise ValueError('Both telegram_to_mastodon and mastodon_to_telegram are disabled, nothing to do.')

        self.mastodon_filter = mastodon_filter(**self.telegram_to_mastodon.filter)
        self.telegram_filter = telegram_filter(**self.mastodon_to_telegram.filter)
        self.mastodon_footer = mastodon_footer(**self.telegram_to_mastodon.footer)
        self.telegram_footer = telegram_footer(**self.mastodon_to_telegram.footer)

    async def _send_media_to_mastodon(self, *messages: Message, footer: str, context: CallbackContext) -> None:

        async def _wait_for_media_ready(media_ids: list[int]) -> None:
            wait_time = 1
            ready = [False for _ in media_ids]
            for _ in range(5):
                for idx, media_id in enumerate(media_ids):
                    try:
                        _ = self.mastodon.media(media_id)
                        logger.info('Media %s is ready', media_id)
                        ready[idx] = True
                    except MastodonAPIError as e:
                        if e.args[1] == 206:
                            # https://docs.joinmastodon.org/methods/media/#206-partial-content
                            logger.info('Media %s is not ready, wait for %d seconds', media_id, wait_time)
                if all(ready):
                    return
                await asyncio.sleep(wait_time)
                wait_time *= 2
            raise TimeoutError('Media is not ready after 5 retries')

        cfg = self.telegram_to_mastodon
        media_ids = []
        text = messages[0].caption or ''
        if not self.mastodon_filter(text):
            logger.info('Do not forward this channel message to mastodon.')
            return
        text += f'\n\n{footer}'
        if cnt := len(messages) > 4:
            logger.warning('Too many medias: %d, it may not be supported by mastodon', cnt)
            return
        with TemporaryDirectory(prefix='mastodon') as tmpdir:
            for message in messages:
                media_type = effective_message_type(message)
                if media_type not in ('photo', 'video'):
                    logger.warning('Unsupported media type: %s', media_type)
                    continue
                media_file = await (message.photo[-1] if media_type == 'photo' else cast(Video, message.effective_attachment)).get_file()
                file_path = os.path.join(tmpdir, media_file.file_unique_id)
                await media_file.download_to_drive(custom_path=file_path)
                media_ids.append(self.mastodon.media_post(file_path).id)
        await _wait_for_media_ready(media_ids)
        status: AttribAccessDict = self.mastodon.status_post(text, visibility='public', media_ids=media_ids)
        success_message = f'*Successfully forward message to mastodon.*\n{status.url}'
        if messages[0].is_automatic_forward:
            await messages[0].reply_markdown(success_message)
        else:
            await context.bot.send_message(cfg.pm_chat_id, success_message, parse_mode=ParseMode.MARKDOWN)

    async def _media_group_sender(self, context: CallbackContext) -> None:
        cfg = self.telegram_to_mastodon
        try:
            if context.job is None:
                logger.warning('No media group context.')
                return
            context.job.data = cast(MediaGroup, context.job.data)
            await self._send_media_to_mastodon(*context.job.data.message, footer=context.job.data.footer, context=context)
        except Exception as exc:
            logger.exception(exc)
            await context.bot.send_message(cfg.pm_chat_id, f'```\n{format_exception(exc)}\n```', parse_mode=ParseMode.MARKDOWN)

    async def _send_message_to_mastodon(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        if message is None:
            logger.warning('No effective message.')
            return
        cfg = self.telegram_to_mastodon
        if message.chat_id != cfg.channel_chat_id:
            logger.warning('Received message from wrong chat id: %d', message.chat_id)
            await message.reply_text('This bot is only for specific channel or chat.')
            return
        logger.info('Received channel message from chat id: %d', message.chat_id)

        try:
            media_type = effective_message_type(message)

            if media_type in ('photo', 'video'):
                if message.effective_attachment is None:
                    logger.warning('No effective attachment.')
                    return
                # media group will be received as multiple updates
                # create a job to wait for all updates and send them together
                # Reference:
                #   https://github.com/Poolitzer/channelforwarder/blob/589104b8a808199ba46d620736bd8bea1dc187d9/main.py#L35-L45

                if message.media_group_id:
                    if context.job_queue is None:
                        logger.error('Cannot get job queue in the context. Ignore this message.')
                        return
                    jobs = context.job_queue.get_jobs_by_name(str(message.media_group_id))
                    if jobs:
                        cast(MediaGroup, jobs[0].context).message.append(message)
                    else:
                        footer = self.mastodon_footer(message)
                        context.job_queue.run_once(self._media_group_sender, 5,
                                                   data=MediaGroup(message=[message], footer=footer),
                                                   name=str(message.media_group_id))
                else:
                    footer = self.mastodon_footer(message)
                    await self._send_media_to_mastodon(message, footer=footer, context=context)
            elif media_type == 'text':
                text = message.text
                if not self.mastodon_filter(text):
                    logger.info('Do not forward this channel message to mastodon.')
                    return
                footer = self.mastodon_footer(message)
                text += f'\n\n{footer}'
                status: AttribAccessDict = self.mastodon.status_post(status=text, visibility='public')
                success_message = f'*Successfully forward message to mastodon.*\n{status.url}'
                if message.is_automatic_forward:
                    await message.reply_markdown(success_message)
                else:
                    await context.bot.send_message(cfg.pm_chat_id, success_message, parse_mode=ParseMode.MARKDOWN)
            else:
                logger.info('Unsupported message type, skip it.')
        except Exception as exc:
            logger.exception(exc)
            await context.bot.send_message(cfg.pm_chat_id, f'```\n{format_exception(exc)}\n```', parse_mode=ParseMode.MARKDOWN)

    async def _send_message_to_telegram(self, status: AttribAccessDict) -> None:
        cfg = self.mastodon_to_telegram
        try:
            if status.account.username == self._mastodon_username and \
                (status.application is None or status.application.name != self._mastodon_app_name) and \
                    self.telegram_filter(status):
                logger.info('Forwarding message from mastodon to telegram.')
                if status.reblog:
                    # check if it is a reblog and get the original message
                    if cfg.forward_reblog_link_only:
                        if status.reblog.visibility != 'public':
                            logger.warning('Cannot forward reblog link to telegram because the original message is not public.')
                            return
                        text = markdownify(self.telegram_footer(status.reblog))
                        logger.info('Sending message to telegram channel:\n %s', text)
                        await self.telegram.bot.send_message(cfg.channel_chat_id, text, parse_mode=ParseMode.MARKDOWN)
                        return
                    status = status.reblog
                text = markdownify(status.content)
                if status.spoiler_text:
                    text = f'*{status.spoiler_text}*\n\n{text}'
                logger.info('Sending message to telegram channel: %s', text)
                text += '\n' + markdownify(self.telegram_footer(status))
                if len(status.media_attachments) > 0:
                    medias: list[InputMediaPhoto | InputMediaVideo] = []
                    for item in status.media_attachments:
                        if item.type == 'image':
                            medias.append(InputMediaPhoto(item.url, parse_mode=ParseMode.MARKDOWN))
                        elif item.type == 'video':
                            medias.append(InputMediaVideo(item.url, parse_mode=ParseMode.MARKDOWN))
                    medias[0].caption = text
                    logger.info('Sending media group to telegram channel.')
                    await self.telegram.bot.send_media_group(cfg.channel_chat_id, medias)
                else:
                    logger.info('Sending pure-text message to telegram channel.')
                    await self.telegram.bot.send_message(cfg.channel_chat_id, text,
                                                         parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        except Exception as exc:
            logger.exception(exc)
            await self.telegram.bot.send_message(cfg.pm_chat_id, f'```\n{format_exception(exc)}\n```', parse_mode=ParseMode.MARKDOWN)

    async def _start(self, update: Update, _: CallbackContext) -> None:
        await update.message.reply_text('Hi!')

    async def _error(self, update: object, context: CallbackContext) -> None:
        logger.warning('Update "%s" caused error "%s"', update, context.error)
        logger.exception(context.error)

    def run(self, dry_run: bool = False) -> None:
        """Run the bridge.
        """
        # Mastodon stream
        if dry_run:
            logger.info('Skip running, because it is a dry run.')
            return
        if not self.mastodon_to_telegram.disable:
            def update_handler(status: AttribAccessDict): return asyncio.run(self._send_message_to_telegram(status))
            listener = CallbackStreamListener(update_handler=update_handler)
            self.mastodon.stream_user(listener=listener, run_async=True, reconnect_async=True)
        else:
            logger.warning('Skip mastodon stream, because mastodon to telegram is disabled.')

        # Telegram bot
        app = self.telegram
        app.add_error_handler(self._error)
        app.add_handler(CommandHandler('start', self._start))
        if not self.telegram_to_mastodon.disable:
            app.add_handler(MessageHandler(UpdateType.CHANNEL_POST, self._send_message_to_mastodon))
        else:
            logger.warning('Skip telegram message handler, because telegram to mastodon is disabled.')
        app.run_polling()
