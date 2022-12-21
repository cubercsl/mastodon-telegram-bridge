import logging
import traceback
from typing import List

from markdownify import MarkdownConverter
from mastodon import AttribAccessDict
from telegram import Message

logger = logging.getLogger(__name__)


class TelegramMarkdownConverter(MarkdownConverter):
    class Options(MarkdownConverter.Options):
        # https://core.telegram.org/bots/api#markdown-style
        autolinks = False
        escape_brackets = True
        escape_backquote = True

    def escape(self, text):
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
    def __init__(self, options):
        self.options = options

    def _forwarded_from(self, name: str) -> str:
        return f'Forwarded from {name}'

    def make_footer(self, _: Message | AttribAccessDict) -> List[str]:
        raise NotImplementedError

    def __call__(self, message: Message | AttribAccessDict) -> str:
        footer = self.make_footer(message)
        return '\n'.join(footer)


class MastodonFooter(Footer):
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

    def make_footer(self, message: Message) -> str:
        footer = []
        if self.options.show_forward_from:
            forwarded_from = self.__get_name(message)
            if forwarded_from:
                footer.append(self._forwarded_from(forwarded_from))
        if self.options.add_link:
            footer.append(self._from(self.__get_link(message)))
        return footer


class TelegramFooter(Footer):
    def make_footer(self, status: AttribAccessDict) -> List[str]:
        footer = []
        if self.options.add_link:
            footer.append(status.url)
        if self.options.tags:
            footer.append(' '.join(f'{tag}' for tag in self.options.tags))
        return footer


def markdownify(text: str, **options) -> str:
    return TelegramMarkdownConverter(**options).convert(text)


def format_exception(exc: Exception) -> str:
    return ''.join(traceback.TracebackException.from_exception(exc).format())
