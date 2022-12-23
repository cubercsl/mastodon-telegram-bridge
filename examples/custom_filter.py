'''
This is an example of a custom filter to filter out the unlisted reblogs in Mastodon.
'''
from typing import Iterable

from mastodon import AttribAccessDict

from mastodon_telegram_bridge.main import main
from mastodon_telegram_bridge.filter import Filter

class ReblogFilter(Filter):
    def __init__(self, *, scope: Iterable[str], rebloged_scope: Iterable[str]):
        self.scope = scope
        self.rebloged_scope = rebloged_scope

    def __call__(self, status: AttribAccessDict) -> bool:
        if status['visibility'] not in self.scope:
            return False
        if status['reblog'] and status['reblog']['visibility'] not in self.rebloged_scope:
            return False
        return True

if __name__ == '__main__':
    main(telegram_filter=ReblogFilter)
