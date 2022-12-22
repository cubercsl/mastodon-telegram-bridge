import os
from tempfile import TemporaryDirectory
from typing import Optional, cast

from mastodon import AttribAccessDict, CallbackStreamListener, Mastodon
from telegram import Bot, InputMediaPhoto, InputMediaVideo, ParseMode, Update, Video
from telegram.ext import CallbackContext, CommandHandler, Filters, MessageHandler, Updater
from telegram.utils.helpers import effective_message_type

from mastodon_telegram_bridge import logger
from mastodon_telegram_bridge.types import (BridgeOptionsDict,
                                             MastodonOptionsDict,
                                             MastodonToTelegramOptions,
                                             MediaDict, MediaGroup,
                                             TelegramOptionsDict,
                                             TelegramToMastodonOptions)
from mastodon_telegram_bridge.utils import MastodonFooter, TelegramFooter, format_exception, markdownify


class Bridge:
    """The bridge between mastodon and telegram.
    """

    def __init__(self, *,
                 telegram: TelegramOptionsDict,
                 mastodon: MastodonOptionsDict,
                 options: Optional[BridgeOptionsDict] = None,
                 telegram_to_mastodon_options: Optional[TelegramToMastodonOptions] = None,
                 mastodon_to_telegram_options: Optional[MastodonToTelegramOptions] = None) -> None:
        """The bridge between mastodon and telegram.

        Args:
            telegram (TelegramOptionsDict): telegram bot options
            mastodon (MastodonOptionsDict): mastodon client options
            options (Optional[BridgeOptionsDict], optional): bridge options. Defaults to None.
            telegram_to_mastodon_options (Optional[TelegramToMastodonOptions], optional): Defaults to None.
            mastodon_to_telegram_options (Optional[MastodonToTelegramOptions], optional): Defaults to None.

        Raises:
            ValueError: options and telegram_to_mastodon_options/mastodon_to_telegram_options are mutually exclusive
            ValueError: options or telegram_to_mastodon_options/mastodon_to_telegram_options must be provided
            ValueError: Both telegram_to_mastodon and mastodon_to_telegram are disabled, nothing to do.
            ValueError: forward_reblog_link_only is only valid if add_link is enabled
        """
        if options is not None:
            if telegram_to_mastodon_options is not None or mastodon_to_telegram_options is not None:
                raise ValueError('options and telegram_to_mastodon_options/mastodon_to_telegram_options are mutually exclusive')
            self.mastodon_to_telegram = MastodonToTelegramOptions(**options['mastodon_to_telegram'])
            self.telegram_to_mastodon = TelegramToMastodonOptions(**options['telegram_to_mastodon'])
        else:
            if telegram_to_mastodon_options is None or mastodon_to_telegram_options is None:
                raise ValueError('options or telegram_to_mastodon_options/mastodon_to_telegram_options must be provided')
            self.mastodon_to_telegram = mastodon_to_telegram_options
            self.telegram_to_mastodon = telegram_to_mastodon_options

        logger.info(self.mastodon_to_telegram)
        logger.info(self.telegram_to_mastodon)
        # check if the tags start with #
        for tags in (self.telegram_to_mastodon.include,
                     self.telegram_to_mastodon.exclude,
                     self.mastodon_to_telegram.tags):
            if any(not tag.startswith('#') for tag in tags):
                raise ValueError('Tags must start with #')

        # check if both telegram_to_mastodon and mastodon_to_telegram are disabled
        if self.telegram_to_mastodon.disable and self.mastodon_to_telegram.disable:
            raise ValueError('Both telegram_to_mastodon and mastodon_to_telegram are disabled, nothing to do.')

        # check if forward_reblog_link_only is enabled without add_link
        if not self.mastodon_to_telegram.disable and not self.mastodon_to_telegram.add_link and \
                self.mastodon_to_telegram.forward_reblog_link_only:
            raise ValueError('forward_reblog_link_only is only valid if add_link is enabled')

        self.mastodon_footer = MastodonFooter(self.telegram_to_mastodon)
        self.telegram_footer = TelegramFooter(self.mastodon_to_telegram)

        # you can add more arguments in [mastodon] section in config.toml to customize the mastodon client
        self.mastodon = Mastodon(**mastodon)
        # you can add more arguments in [telegram] section in config.toml to customize the telegram bot
        self.bot = Bot(**telegram)

        self.mastodon_username: str = self.mastodon.me().username
        self.mastodon_app_name: str = self.mastodon.app_verify_credentials().name
        logger.info('Username: %s, App name: %s', self.mastodon_username, self.mastodon_app_name)

    def _should_forward_to_mastodon(self, msg: str) -> bool:
        excluded = any(tag in msg for tag in self.telegram_to_mastodon.exclude)
        if include := self.telegram_to_mastodon.include:
            return any(tag in msg for tag in include) and not excluded
        return not excluded

    def _should_forward_to_telegram(self, status: AttribAccessDict) -> bool:
        # check if the message is from the telegram channel or another app
        return status.account.username == self.mastodon_username and \
            (status.application is None or status.application.name != self.mastodon_app_name) and \
            status.in_reply_to_id is None and \
            status.visibility in self.mastodon_to_telegram.scope

    def _send_media_to_mastodon(self, *medias: MediaDict, footer: str, context: CallbackContext) -> None:
        cfg = self.telegram_to_mastodon
        media_ids = []
        text = medias[0].caption
        if not self._should_forward_to_mastodon(text):
            logger.info('Do not forward this channel message to mastodon.')
            return
        text += '\n' + footer
        if cnt := len(medias) > 4:
            logger.warning('Too many medias: %d, it may not be supported by mastodon', cnt)
            return
        with TemporaryDirectory(prefix='mastodon') as tmpdir:
            for media_type, media_file, _ in medias:
                if media_type not in ('photo', 'video'):
                    logger.warning('Unsupported media type: %s', media_type)
                    continue
                file_path = os.path.join(tmpdir, media_file.file_unique_id)
                media_file.download(custom_path=file_path)
                media_ids.append(self.mastodon.media_post(file_path).id)
        status: AttribAccessDict = self.mastodon.status_post(text, visibility='public', media_ids=media_ids)
        context.bot.send_message(
            cfg.pm_chat_id, f'*Successfully forward message to mastodon.*\n{status.url}', parse_mode=ParseMode.MARKDOWN)

    def _media_group_sender(self, context: CallbackContext) -> None:
        cfg = self.telegram_to_mastodon
        try:
            if context.job is None:
                logger.warning('No media group context.')
                return
            context.job.context = cast(MediaGroup, context.job.context)
            self._send_media_to_mastodon(*context.job.context.medias, footer=context.job.context.footer, context=context)
        except Exception as exc:
            logger.exception(exc)
            context.bot.send_message(cfg.pm_chat_id, f'```\n{format_exception(exc)}\n```', parse_mode=ParseMode.MARKDOWN)

    def _send_message_to_mastodon(self, update: Update, context: CallbackContext) -> None:
        message = update.effective_message
        if message is None:
            logger.warning('No effective message.')
            return
        cfg = self.telegram_to_mastodon
        if message.chat_id != cfg.channel_chat_id:
            logger.warning('Received message from wrong channel id: %d', message.chat_id)
            message.reply_text('This bot is only for specific channel.')
            return
        logger.info('Received channel message from channel id: %d', message.chat_id)
        try:
            media_type = effective_message_type(message)

            if media_type in ('photo', 'video'):
                if message.effective_attachment is None:
                    logger.warning('No effective attachment.')
                    return

                media_file = message.photo[-1].get_file() \
                    if media_type == 'photo' else cast(Video, message.effective_attachment).get_file()
                media_dict = MediaDict(media_file=media_file, media_type=media_type, caption=message.caption)

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
                        cast(MediaGroup, jobs[0].context).medias.append(media_dict)
                    else:
                        footer = self.mastodon_footer(message)
                        context.job_queue.run_once(self._media_group_sender, 5,
                                                   context=(MediaGroup(medias=[media_dict], footer=footer)),
                                                   name=str(message.media_group_id))
                else:
                    footer = self.mastodon_footer(message)
                    self._send_media_to_mastodon(media_dict, footer=footer, context=context)
            elif media_type == 'text':
                text = message.text
                if not self._should_forward_to_mastodon(text):
                    logger.info('Do not forward this channel message to mastodon.')
                    return
                footer = self.mastodon_footer(message)
                text += '\n' + footer
                status: AttribAccessDict = self.mastodon.status_post(status=text, visibility='public')
                context.bot.send_message(
                    cfg.pm_chat_id, f'*Successfully forward message to mastodon.*\n{status.url}', parse_mode=ParseMode.MARKDOWN)
            else:
                logger.info('Unsupported message type, skip it.')
        except Exception as exc:
            logger.exception(exc)
            context.bot.send_message(cfg.pm_chat_id, f'```\n{format_exception(exc)}\n```', parse_mode=ParseMode.MARKDOWN)

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
                logger.info('Sending message to telegram channel: %s', text)
                text += '\n' + self.telegram_footer(status)
                if len(status.media_attachments) > 0:
                    medias: list[InputMediaPhoto | InputMediaVideo] = []
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
            self.bot.send_message(cfg.pm_chat_id, f'```\n{format_exception(exc)}\n```', parse_mode=ParseMode.MARKDOWN)

    def _start(self, update: Update, _: CallbackContext) -> None:
        update.message.reply_text('Hi!')

    def _error(self, update: object, context: CallbackContext) -> None:
        logger.warning('Update "%s" caused error "%s"', update, context.error)
        logger.exception(context.error)

    def run(self) -> None:
        """Run the bridge.
        """
        # Mastodon stream
        if not self.mastodon_to_telegram.disable:
            listener = CallbackStreamListener(update_handler=self._send_message_to_telegram)
            self.mastodon.stream_user(listener=listener, run_async=True)
        else:
            logger.warning('Skip mastodon stream, because mastodon to telegram is disabled.')

        # Telegram bot
        updater = Updater(bot=self.bot, use_context=True)
        dispatcher = updater.dispatcher
        dispatcher.add_error_handler(self._error)
        dispatcher.add_handler(CommandHandler('start', self._start))
        if not self.telegram_to_mastodon.disable:
            dispatcher.add_handler(MessageHandler(Filters.update.channel_post, self._send_message_to_mastodon))
        else:
            logger.warning('Skip telegram message handler, because telegram to mastodon is disabled.')
        updater.start_polling()
        updater.idle()
