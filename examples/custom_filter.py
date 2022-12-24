'''
This is an example of a custom filter to filter out the unlisted reblogs in Mastodon.
'''
from typing import Iterable

from mastodon import AttribAccessDict

from mastodon_telegram_bridge import Filter, main


class ReblogFilter(Filter):
    def __init__(self, *, scope: Iterable[str], rebloged_scope: Iterable[str], **kwargs: Any):
        super().__init__(**kwargs)
        self.scope = scope
        self.rebloged_scope = rebloged_scope

    def __call__(self, status: AttribAccessDict) -> bool:
        if status['visibility'] not in self.scope:
            return False
        if status['reblog'] and status['reblog']['visibility'] not in self.rebloged_scope:
            return False
        return status.in_reply_to_id is None and \
            status.visibility in self.scope


if __name__ == '__main__':
    main(telegram_filter=ReblogFilter)
