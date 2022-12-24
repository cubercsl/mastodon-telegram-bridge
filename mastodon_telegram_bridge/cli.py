import argparse
from typing import Type, cast, overload

import betterlogging as logging
import tomli

from ._version import __version__ as version
from .bridge import Bridge
from .filter import Filter
from .footer import Footer
from .typing import ConfigDict


@overload
def main(*, mastodon_filter: Type[Filter]) -> None: ...
@overload
def main(*, telegram_filter: Type[Filter]) -> None: ...
@overload
def main(*, mastodon_footer: Type[Footer]) -> None: ...
@overload
def main(*, telegram_footer: Type[Footer]) -> None: ...
@overload
def main(*, mastodon_filter: Type[Filter], telegram_filter: Type[Filter]) -> None: ...
@overload
def main(*, mastodon_filter: Type[Filter], mastodon_footer: Type[Footer]) -> None: ...
@overload
def main(*, mastodon_filter: Type[Filter], telegram_footer: Type[Footer]) -> None: ...
@overload
def main(*, telegram_filter: Type[Filter], mastodon_footer: Type[Footer]) -> None: ...
@overload
def main(*, telegram_filter: Type[Filter], telegram_footer: Type[Footer]) -> None: ...
@overload
def main(*, mastodon_footer: Type[Footer], telegram_footer: Type[Footer]) -> None: ...
@overload
def main(*, mastodon_filter: Type[Filter], telegram_filter: Type[Filter], mastodon_footer: Type[Footer]) -> None: ...
@overload
def main(*, mastodon_filter: Type[Filter], telegram_filter: Type[Filter], telegram_footer: Type[Footer]) -> None: ...
@overload
def main(*, mastodon_filter: Type[Filter], mastodon_footer: Type[Footer], telegram_footer: Type[Footer]) -> None: ...
@overload
def main(*, telegram_filter: Type[Filter], mastodon_footer: Type[Footer], telegram_footer: Type[Footer]) -> None: ...


@overload
def main(*,
         mastodon_filter: Type[Filter], telegram_filter: Type[Filter],
         mastodon_footer: Type[Footer], telegram_footer: Type[Footer]) -> None: ...


def main(**kwargs) -> None:
    parser = argparse.ArgumentParser('mastodon-telegram-bridge',
                                     description=f'A simple telegram bot bridges mastodon timeline. {version}')
    parser.add_argument('config', help='config file path', nargs='?', default='config.toml')
    parser.add_argument('-v', '--verbose', help='verbose mode', action='store_true')
    parser.add_argument('-s', '--silent', help='silent mode', action='store_true')
    parser.add_argument('-V', '--version', help='show version', action='version', version=version)
    parser.add_argument('--dry-run', help='dry run', action='store_true')
    args = parser.parse_args()
    if args.verbose:
        level = logging.DEBUG
    elif args.silent:
        level = logging.WARNING
    else:
        level = logging.INFO

    logging.basic_colorized_config(level=level)

    with open(args.config, 'rb') as cfg:
        config = cast(ConfigDict, tomli.load(cfg))
    bridge = Bridge(**config, **kwargs)
    bridge.run(dry_run=args.dry_run)
