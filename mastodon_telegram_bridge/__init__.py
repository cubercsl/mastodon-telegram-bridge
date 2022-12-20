import logging
import traceback
from typing import List

from markdownify import MarkdownConverter
from mastodon import AttribAccessDict
from telegram import Message

logger = logging.getLogger(__name__)


class TelegramMarkdownConverter(MarkdownConverter):
    def __init__(self, **options):
        # https://core.telegram.org/bots/api#markdown-style
        options['autolinks'] = False
        options['escape_brackets'] = True
        options['escape_backquote'] = True
        super().__init__(**options)

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
    def __init__(self):
        pass

    def _forwarded_from(self, name: str) -> str:
        return f'Forwarded from {name}'

    def _from(self, link: str) -> str:
        return f'from {link}'

    def make_footer(self, _: Message | AttribAccessDict) -> List[str]:
        raise NotImplementedError

    def __call__(self, message: Message | AttribAccessDict) -> str:
        footer = self.make_footer(message)
        return '\n'.join(footer)


class MastodonFooter(Footer):
    def __init__(self, **options):
        super().__init__()
        self.add_link_in_mastodon = options.get('add_link_in_mastodon', False)
        self.show_forward_info = options.get('show_forward_info', False)

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
        if self.show_forward_info:
            forwarded_from = self.__get_name(message)
            if forwarded_from:
                footer.append(self._forwarded_from(forwarded_from))
        if self.add_link_in_mastodon:
            footer.append(self._from(self.__get_link(message)))
        return footer


class TelegramFooter(Footer):
    def __init__(self, **options):
        super().__init__()
        self.add_link_in_telegram = options.get('add_link_in_telegram', False)

    def make_footer(self, status: AttribAccessDict) -> List[str]:
        footer = []
        if self.add_link_in_telegram:
            footer.append(self._from(status.url))
        return footer


def markdownify(text: str, **options) -> str:
    return TelegramMarkdownConverter(**options).convert(text)


def format_exception(exc: Exception) -> str:
    return ''.join(traceback.TracebackException.from_exception(exc).format())
