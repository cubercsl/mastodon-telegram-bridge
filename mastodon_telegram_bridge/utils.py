import traceback
from typing import List

from betterlogging.outer.better_exceptions import ExceptionFormatter
from markdownify import MarkdownConverter
from mastodon import AttribAccessDict
from telegram import Message

from mastodon_telegram_bridge.types import MastodonToTelegramOptions, TelegramToMastodonOptions


class TelegramMarkdownConverter(MarkdownConverter):
    """Telegram Markdown Converter

    Convert markdown to telegram markdown style
    """
    class Options(MarkdownConverter.Options):
        """Markdown Converter Options

        Options for markdown converter
        Reference: https://core.telegram.org/bots/api#markdown-style
        """
        autolinks = False
        escape_brackets = True
        escape_backquote = True

    def escape(self, text: str) -> str:
        """Escape some characters

        Args:
            text (str): text to escape

        Returns:
            str: escaped text 
        """
        if not text:
            return ''
        if self.options['escape_asterisks']:
            text = text.replace('*', r'\*')
        if self.options['escape_underscores']:
            text = text.replace('_', r'\_')
        if self.options['escape_brackets']:
            text = text.replace('[', r'\[')
        if self.options['escape_backquote']:
            text = text.replace('`', r'\`')
        return text


class Footer:
    """The footer of a message 
    """

    def _forwarded_from(self, name: str) -> str:
        return f'Forwarded from {name}'

    def make_footer(self, _: Message | AttribAccessDict) -> List[str]:
        raise NotImplementedError

    def __call__(self, message: Message | AttribAccessDict) -> str:
        footer = self.make_footer(message)
        return '\n'.join(footer)


class MastodonFooter(Footer):
    """Footer for mastodon statuses
    """

    def __init__(self, options: TelegramToMastodonOptions):
        self.options = options

    def __get_name(self, message: Message) -> str:
        if message.forward_from:
            return message.forward_from.name
        if message.forward_from_chat:
            return message.forward_from_chat.title
        if message.forward_sender_name:
            return message.forward_sender_name
        return ''

    def __get_link(self, message: Message) -> str:
        return f'https://t.me/c/{str(message.chat_id)[4:]}/{message.message_id}'

    def make_footer(self, message: Message) -> List[str]:
        """generate footer

        Args:
            message (Message): the message from telegram

        Returns:
            List[str]: footer lines in list
        """
        footer = []
        if self.options.show_forward_from:
            forward_from = self.__get_name(message)
            if forward_from:
                footer.append(self._forwarded_from(forward_from))
        if self.options.add_link:
            footer.append(self.__get_link(message))
        return footer


class TelegramFooter(Footer):
    """Footer for telegram messages
    """

    def __init__(self, options: MastodonToTelegramOptions):
        self.options = options

    def make_footer(self, status: AttribAccessDict) -> List[str]:
        """generate footer

        Args:
            status (AttribAccessDict): the status dict from mastodon

        Returns:
            List[str]: footer lines in list
        """
        footer = []
        if self.options.add_link:
            footer.append(status.url)
        if self.options.tags:
            footer.append(' '.join(f'{tag}' for tag in self.options.tags))
        return footer


def markdownify(text: str, **options) -> str:
    """Markdownify text to telegram markdown style

    Args:
        text (str): text to convert

    Returns:
        str: converted text
    """
    return TelegramMarkdownConverter(**options).convert(text)


def format_exception(exc: Exception) -> str:
    """Format exception to string

    Args:
        exc (Exception): exception to format

    Returns:
        str: formatted exception
    """
    return ''.join(ExceptionFormatter().format_exception(exc))
