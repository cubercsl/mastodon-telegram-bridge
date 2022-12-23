from typing import Any, Iterable

from mastodon import AttribAccessDict


class Filter:
    """Filter for messages

    Allow user to add a custom filter to a message

    Inherit from this class to implement a filter for a specific platform

    Example:
        >>> class MyFilter(Filter):
        ...     def __init__(self, *, pattern: str):
        ...         self.pattern = pattern
        ...     def __call__(self, message: str) -> bool:
        ...         return re.match(self.pattern, message)
        >>> filter = MyFilter(pattern='^foo')
        >>> filter('foo')
        True
        >>> filter('bar')
        False
        >>> filter('foobar')
        True
        >>> filter('barfoo')
        False
    """

    def __init__(self) -> None:
        pass

    def __call__(self, _: Any) -> bool:
        """Filter message, check if it should be forwarded

        Args:
            message (Any): The message to filter

        Returns:
            bool: True if message should can be forwarded
        """
        raise NotImplementedError

    @classmethod
    def from_dict(cls, config: dict) -> 'Filter':
        """Create a filter from dict

        Args:
            config (dict): config

        Returns:
            Filter: the filter

        Raises:
            ValueError: if config is invalid
        """
        return cls(**config)


class MastodonFilter(Filter):

    def __init__(self, *, include: Iterable[str], exclude: Iterable[str]) -> None:
        self.include = include
        self.exclude = exclude
        self.__check_tags()

    def __check_tags(self) -> None  :
        if not isinstance(self.include, Iterable):
            raise ValueError(f'include must be an iterable, got: {type(self.include)}')
        if not isinstance(self.exclude, Iterable):
            raise ValueError(f'exclude must be an iterable, got: {type(self.exclude)}')
        if not all(isinstance(tag, str) for tag in self.include):
            raise ValueError(f'include tags must be strings, got: {type(self.include)}')
        if not all(isinstance(tag, str) for tag in self.exclude):
            raise ValueError(f'exclude tags must be strings, got: {type(self.exclude)}')
        for tag in self.include:
            if tag in self.exclude:
                raise ValueError(f'include and exclude tags overlap: {tag}')
        if not all(tag.startswith('#') for tag in self.include):
            raise ValueError(f'include tags must start with #, got: {self.include}')
        if not all(tag.startswith('#') for tag in self.exclude):
            raise ValueError(f'exclude tags must start with #, got: {self.exclude}')

    def __call__(self, text: str) -> bool:
        excluded = any(tag in text for tag in self.exclude)
        if include := self.include:
            return any(tag in text for tag in include) and not excluded
        return not excluded


class TelegramFilter(Filter):

    def __init__(self, *, scope: Iterable[str]) -> None:
        self.scope = scope
        self.__check_scope()

    def __check_scope(self):
        if self.scope and any(scope not in ('public', 'unlisted', 'private', 'direct') for scope in self.scope):
            raise ValueError('scope must be one of public, unlisted, private or direct')

    def __call__(self, status: AttribAccessDict) -> bool:
        return status.in_reply_to_id is None and \
            status.visibility in self.scope
