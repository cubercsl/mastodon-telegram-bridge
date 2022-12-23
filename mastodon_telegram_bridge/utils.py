from betterlogging.outer.better_exceptions import ExceptionFormatter
from markdownify import MarkdownConverter


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
