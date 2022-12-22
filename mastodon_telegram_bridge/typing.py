from typing import List, Literal, TypedDict

from telegram import File


class MediaDict(TypedDict):
    media_type: Literal['photo', 'video']
    media_file: File
    caption: str


class MastodonToTelegramDict(TypedDict):
    disable: bool
    channel_chat_id: int
    pm_chat_id: int
    scope: List[str]
    tags: List[str]
    add_link: bool
    forward_reblog_link_only: bool


class TelegramToMastodonDict(TypedDict):
    disable: bool
    channel_chat_id: int
    pm_chat_id: int
    add_link: bool
    show_forward_from: bool
    include: List[str]
    exclude: List[str]


class BridgeOptionsDict(TypedDict):
    telegram_to_mastodon: TelegramToMastodonDict
    mastodon_to_telegram: MastodonToTelegramDict
