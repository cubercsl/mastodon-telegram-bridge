import logging
import traceback

from markdownify import MarkdownConverter

logger = logging.getLogger(__name__)


class TelegramMarkdownConverter(MarkdownConverter):
    def __init__(self, **options):
        # https://core.telegram.org/bots/api#markdown-style
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


def markdownify(text: str, **options) -> str:
    return TelegramMarkdownConverter(**options).convert(text)


def format_exception(exc: Exception) -> str:
    return ''.join(traceback.TracebackException.from_exception(exc).format())
