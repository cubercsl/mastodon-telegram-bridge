from tempfile import TemporaryDirectory

from mastodon import AttribAccessDict, CallbackStreamListener, Mastodon
from telegram import (Bot, InputMediaPhoto, InputMediaVideo, Message,
                      ParseMode, Update)
from telegram.ext import (CallbackContext, CommandHandler, Dispatcher, Filters,
                          MessageHandler, Updater)

from mastodon_telegram_bridge import format_exception, logger, markdownify


class Bridge(object):
    def __init__(self, config):
        self.config = config
        self.mastodon = Mastodon(access_token=config.mastodon_api_access_token,
                                 api_base_url=config.mastodon_host)
        self.bot = Bot(token=config.tg_bot_token)

    @staticmethod
    def _get_forward_name(message: Message) -> str | None:
        if message.forward_from:
            return message.forward_from.name
        if message.forward_from_chat:
            return message.forward_from_chat.title
        if message.forward_sender_name:
            return message.forward_sender_name
        return None

    def _should_forward_to_telegram(self, status: AttribAccessDict) -> bool:
        # check if the message is from the telegram channel or another app
        return status.account.username == self.config.mastodon_username and \
            (status.application is None or status.application.name != self.config.mastodon_app_name) and \
            status.in_reply_to_id is None and \
            status.visibility in self.config.scope

    def _send_message_to_mastodon(self, update: Update, context: CallbackContext) -> None:
        channel_post = update.channel_post
        if channel_post.chat_id != self.config.channel_chat_id:
            logger.warning(
                f'Received message from wrong channel id: {channel_post.chat_id}')
            channel_post.reply_text(
                "This bot is only for specific channel.")
            return
        logger.info(
            f'Received channel message from channel id: {channel_post.chat_id}')
        try:
            forawrd = self._get_forward_name(channel_post)
            media_ids = None
            text = ''

            if channel_post.photo:
                if channel_post.media_group_id:
                    logger.info('This is a media group. Skip it.')
                    return
                with TemporaryDirectory(prefix='mastodon') as tmpdir:
                    text = channel_post.caption or ''
                    if any(tag in text for tag in self.config.noforward_tags):
                        logger.info(
                            'Do not forward this channel message to mastodon.')
                        return
                    file_path = f'{tmpdir}/{channel_post.photo[-1].file_unique_id}'
                    channel_post.photo[-1].get_file().download(
                        custom_path=file_path)
                    media_ids = self.mastondon.media_post(file_path).id
            elif channel_post.video:
                with TemporaryDirectory(prefix='mastodon') as tmpdir:
                    text = channel_post.caption or ''
                    if any(tag in text for tag in self.config.noforward_tags):
                        logger.info(
                            'Do not forward this channel message to mastodon.')
                        return
                    file_path = f'{tmpdir}/{channel_post.video.file_name}'
                    channel_post.video.get_file().download(custom_path=file_path)
                    media_ids = self.mastondon.media_post(file_path).id
            elif channel_post.text:
                text = channel_post.text
                if any(tag in text for tag in self.config.noforward_tags):
                    logger.info(
                        'Do not forward this channel message to mastodon.')
                    return
                if forawrd:
                    text += f'\n\nForwarded from telegram: {forawrd}'
                if self.config.add_link_in_mastodon:
                    link = f'from: https://t.me/c/{str(channel_post.chat_id)[4:]}/{channel_post.message_id}'
                    text += f'\n\n{link}'
            else:
                logger.info(f'Unsupported message type, skip it.')
                return

            if self.config.show_forward_info and forawrd:
                text += f'\n\nForwarded from {forawrd}'
            if self.config.add_link_in_mastodon:
                link = f'from: https://t.me/c/{str(channel_post.chat_id)[4:]}/{channel_post.message_id}'
                text += f'\n\n{link}'
            self.mastondon.status_post(
                status=text, visibility='public', media_ids=media_ids)
            context.bot.send_message(
                self.config.pm_chat_id, f'Successfully forward message to mastodon.\n{text}')
        except Exception as e:
            logger.exception(e)
            context.bot.send_message(
                self.config.pm_chat_id, f'```{format_exception(e)}```', parse_mode=ParseMode.MARKDOWN)

    def _send_message_to_telegram(self, status: AttribAccessDict) -> None:
        try:
            if self._should_forward_to_telegram(status):
                logger.info(f'Forwarding message from mastodon to telegram.')
                if status.reblog:
                    # check if it is a reblog
                    # get the original message
                    status = status.reblog
                txt = markdownify(status.content)
                if self.config.add_link_in_telegram:
                    txt += f"from: {status.url}"
                logger.info(f'Sending message to telegram channel: {txt}')
                if len(status.media_attachments) > 0:
                    medias = []
                    for item in status.media_attachments:
                        if item.type == 'image':
                            medias.append(InputMediaPhoto(
                                item.url, parse_mode=ParseMode.MARKDOWN))
                        elif item.type == 'video':
                            medias.append(InputMediaVideo(
                                item.url, parse_mode=ParseMode.MARKDOWN))
                    medias[0].caption = txt
                    logger.info('Sending media group to telegram channel.')
                    self.bot.send_media_group(
                        self.config.channel_chat_id, medias)
                else:
                    logger.info(
                        'Sending pure-text message to telegram channel.')
                    self.bot.send_message(
                        self.config.channel_chat_id, txt, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        except Exception as e:
            logger.exception(e)
            self.bot.send_message(
                self.config.pm_chat_id, f'```{format_exception(e)}```', parse_mode=ParseMode.MARKDOWN)

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
        dp: Dispatcher = updater.dispatcher
        dp.add_error_handler(self._error)
        dp.add_handler(CommandHandler('start', self._start))
        dp.add_handler(MessageHandler(
            Filters.update.channel_post, self._send_message_to_mastodon))
        updater.start_polling()
        updater.idle()
