from typing import Iterable, Literal, MutableSequence, NamedTuple, Optional, TypedDict

from telegram import Message


class MediaGroup(NamedTuple):
    """MediaGroup
    """
    message: MutableSequence[Message]
    footer: str


class TelegramOptionsDict(TypedDict):
    """TelegramOptionsDict
    """
    token: str


class MastodonOptionsDict(TypedDict):
    """MastodonOptionsDict
    """
    api_base_url: str
    access_token: str


class MastodonToTelegramOptionsDict(TypedDict):
    """Mastodon To Telegram Options Dict
    """
    disable: bool
    channel_chat_id: int
    pm_chat_id: int
    scope: Iterable[str]
    tags: Iterable[str]
    add_link: bool
    forward_reblog_link_only: bool


class TelegramToMastodonOptionsDict(TypedDict):
    """Telegram To Mastodon Options Dict
    """
    disable: bool
    channel_chat_id: int
    pm_chat_id: int
    add_link: bool
    show_forward_from: bool
    include: Iterable[str]
    exclude: Iterable[str]


class BridgeOptionsDict(TypedDict):
    """Bridge Options Dict
    """
    telegram_to_mastodon: TelegramToMastodonOptionsDict
    mastodon_to_telegram: MastodonToTelegramOptionsDict


class MastodonToTelegramOptions(NamedTuple):
    """Mastodon To Telegram Options
    """
    disable: bool = False
    channel_chat_id: int = 0
    pm_chat_id: int = 0
    scope: Iterable[str] = ("public", "unlisted")
    tags: Iterable[str] = ()
    add_link: bool = True
    forward_reblog_link_only: bool = True


class TelegramToMastodonOptions(NamedTuple):
    """Telegram To Mastodon Options
    """
    disable: bool = False
    channel_chat_id: int = 0
    pm_chat_id: int = 0
    add_link: bool = False
    show_forward_from: bool = True
    include: Iterable[str] = ()
    exclude: Iterable[str] = ("#nofwd", "#noforward")
