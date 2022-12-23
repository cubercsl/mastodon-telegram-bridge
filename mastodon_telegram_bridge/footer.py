
from typing import Iterable, Optional

from mastodon import AttribAccessDict
from telegram import Message


class Footer:
    """The footer of a message 

    Allow user to add a custom footer to a message

    Inherit from this class to implement a footer for a specific platform

    Example:
        >>> class MyFooter(Footer):
        ...     def make_footer(self, message: Message) -> list[str]:
        ...        return [f'This is a footer for {message.id}', f'From {message.from_user.name}', f'Link: {message.link}']
        >>> footer = MyFooter()
        >>> footer(Message(id=1, from_user=User(name='foo'), link='https://example.com/1'))
        'This is a footer for 1\\nFrom foo\\nLink: https://example.com/1'
        >>> footer(Message(id=2, from_user=User(name='bar'), link='https://example.com/2'))
        'This is a footer for 2\\nFrom bar\\nLink: https://example.com/2'
    """

    def __init__(self, *args, **kwargs) -> None:
        pass

    def _forwarded_from(self, name: str) -> str:
        return f'Forwarded from {name}'

    def make_footer(self, _: Message | AttribAccessDict) -> list[str]:
        raise NotImplementedError

    def __call__(self, message: Message | AttribAccessDict) -> str:
        footer = self.make_footer(message)
        return '\n'.join(footer)


class MastodonFooter(Footer):
    """Footer for mastodon statuses
    """

    def __init__(self, *, add_link: bool, show_forward_from: bool):
        self.add_link = add_link
        self.show_forward_from = show_forward_from

    def __get_forward_name(self, message: Message) -> Optional[str]:
        if message.forward_from:
            return message.forward_from.name
        if message.forward_from_chat:
            return message.forward_from_chat.title
        if message.forward_sender_name:
            return message.forward_sender_name
        return None

    def __get_forward_link(self, message: Message) -> Optional[str]:
        if message.forward_from_chat and (chat_link := message.forward_from_chat.link):
            return f'{chat_link}/{message.forward_from_message_id}'
        return None

    def make_footer(self, message: Message) -> list[str]:
        """generate footer

        Args:
            message (Message): the message from telegram

        Returns:
            List[str]: footer lines in list
        """
        footer = []
        if self.show_forward_from:
            if forward_from := self.__get_forward_name(message):
                footer.append(self._forwarded_from(forward_from))
            if forward_link := self.__get_forward_link(message):
                footer.append(forward_link)
        if self.add_link and message.link is not None:
            footer.append(message.link)
        return footer


class TelegramFooter(Footer):
    """Footer for telegram messages
    """

    def __init__(self, *, add_link: bool, tags: Iterable[str]):
        self.add_link = add_link
        self.tags = tags

    def make_footer(self, status: AttribAccessDict) -> list[str]:
        """generate footer

        Args:
            status (AttribAccessDict): the status dict from mastodon

        Returns:
            List[str]: footer lines in list
        """
        footer = []
        if self.add_link:
            footer.append(status.url)
        if self.tags:
            footer.append(' '.join(f'{tag}' for tag in self.tags))
        return footer
