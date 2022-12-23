from typing import Iterable, MutableSequence, NamedTuple, Type, TypedDict

from telegram import Message

from mastodon_telegram_bridge.filter import Filter
from mastodon_telegram_bridge.footer import Footer


class MediaGroup(NamedTuple):
    """MediaGroup
    """
    message: MutableSequence[Message]
    footer: str


class OptionsDict(TypedDict):
    """Options Dict
    """
    pass


class CustomArgs(TypedDict, total=False):
    """Custom Args
    """
    mastodon_filter: Type[Filter]
    mastodon_footer: Type[Footer]
    telegram_filter: Type[Filter]
    telegram_footer: Type[Footer]


class TelegramOptionsDict(TypedDict):
    """TelegramOptionsDict
    """
    token: str


class MastodonOptionsDict(TypedDict):
    """MastodonOptionsDict
    """
    api_base_url: str
    access_token: str


class MastodonToTelegramFilterOptionsDict(TypedDict):
    """Mastodon To Telegram Filter Options Dict
    """
    scope: Iterable[str]


class MastodonToTelegramFooterOptionsDict(TypedDict):
    """Mastodon To Telegram Footer Options Dict
    """
    add_link: bool
    tags: Iterable[str]


class MastodonToTelegramOptionsDict(TypedDict):
    """Mastodon To Telegram Options Dict
    """
    disable: bool
    channel_chat_id: int
    pm_chat_id: int
    forward_reblog_link_only: bool
    filter: OptionsDict
    footer: OptionsDict


class TelegramToMastodonFooterOptionsDict(TypedDict):
    """Telegram To Mastodon Footer Options Dict
    """
    add_link: bool
    show_forward_from: bool


class TelegramToMastodonFilterOptionsDict(TypedDict):
    """Telegram To Mastodon Filter Options Dict
    """
    include: Iterable[str]
    exclude: Iterable[str]


class TelegramToMastodonOptionsDict(TypedDict):
    """Telegram To Mastodon Options Dict
    """
    disable: bool
    channel_chat_id: int
    pm_chat_id: int
    filter: OptionsDict
    footer: OptionsDict


class BridgeOptionsDict(TypedDict):
    """Bridge Options Dict
    """
    telegram_to_mastodon: TelegramToMastodonOptionsDict
    mastodon_to_telegram: MastodonToTelegramOptionsDict


# Config Dict Types loaded from config.toml
class ConfigDict(TypedDict):
    """Options Dict
    """
    telegram: TelegramOptionsDict
    mastodon: MastodonOptionsDict
    options: BridgeOptionsDict


# Bridge Options


class MastodonToTelegramOptions(NamedTuple):
    """Mastodon To Telegram Options
    """
    disable: bool = False
    channel_chat_id: int = 0
    pm_chat_id: int = 0
    forward_reblog_link_only: bool = True
    filter: OptionsDict = MastodonToTelegramFilterOptionsDict(
        scope=["public", "unlisted"],
    )
    footer: OptionsDict = MastodonToTelegramFooterOptionsDict(
        add_link=True,
        tags=["#mastodon"],
    )


class TelegramToMastodonOptions(NamedTuple):
    """Telegram To Mastodon Options
    """
    disable: bool = False
    channel_chat_id: int = 0
    pm_chat_id: int = 0
    filter: OptionsDict = TelegramToMastodonFilterOptionsDict(
        include=[],
        exclude=["#nofwd", "#noforward", "#mastodon"],
    )
    footer: OptionsDict = TelegramToMastodonFooterOptionsDict(
        add_link=False,
        show_forward_from=True,
    )
