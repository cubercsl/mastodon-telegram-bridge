import logging
from typing import List

logger = logging.getLogger(__name__)


class BridgeOptions:
    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.__dict__})'


class MastodonToTelegramOptions(BridgeOptions):
    def __init__(self):
        self.disable: bool = False
        self.channel_chat_id: int = 0
        self.pm_chat_id: int = 0
        self.scope: List[str] = ["public", "unlisted"]
        self.tags: List[str] = []
        self.add_link: bool = True
        self.forward_reblog_link_only: bool = True


class TelegramToMastodonOptions(BridgeOptions):
    def __init__(self):
        self.disable: bool = False
        self.channel_chat_id: int = 0
        self.pm_chat_id: int = 0
        self.add_link: bool = False
        self.show_forward_from: bool = True
        self.include: List[str] = []
        self.exclude: List[str] = []
