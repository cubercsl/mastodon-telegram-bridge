import logging
from typing import Iterable, List

logger = logging.getLogger(__name__)


class BridgeOptions:
    def __repr__(self):
        return f'{self.__class__.__name__}({self.__dict__})'


class MastodonToTelegramOptions(BridgeOptions):
    def __init__(self, *,
                 disable: bool = False,
                 channel_chat_id: int = 0,
                 pm_chat_id: int = 0,
                 scope: Iterable[str] = ("public", "unlisted"),
                 tags: Iterable[str] = (),
                 add_link: bool = True,
                 forward_reblog_link_only: bool = True):
        self.disable: bool = disable
        self.channel_chat_id: int = channel_chat_id
        self.pm_chat_id: int = pm_chat_id
        self.scope: List[str] = list(scope)
        self.tags: List[str] = list(tags)
        self.add_link: bool = add_link
        self.forward_reblog_link_only: bool = forward_reblog_link_only


class TelegramToMastodonOptions(BridgeOptions):
    def __init__(self, *,
                 disable: bool = False,
                 channel_chat_id: int = 0,
                 pm_chat_id: int = 0,
                 add_link: bool = False,
                 show_forward_from: bool = True,
                 include: Iterable[str] = (),
                 exclude: Iterable[str] = ("#nofwd", "#noforward")):
        self.disable: bool = disable
        self.channel_chat_id: int = channel_chat_id
        self.pm_chat_id: int = pm_chat_id
        self.add_link: bool = add_link
        self.show_forward_from: bool = show_forward_from
        self.include: List[str] = list(include)
        self.exclude: List[str] = list(exclude)
