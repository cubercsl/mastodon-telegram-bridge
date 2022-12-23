import argparse
from typing import cast

import betterlogging as logging
import tomli


from ._version import __version__
from .bridge import Bridge
from .typing import ConfigDict


def main(**kwargs) -> None:
    parser = argparse.ArgumentParser('mastodon-telegram-bridge',
                                     description=f'A simple telegram bot bridges mastodon timeline. {__version__}')
    parser.add_argument('config', help='config file path', nargs='?', default='config.toml')
    parser.add_argument('-v', '--verbose', help='verbose mode', action='store_true')
    parser.add_argument('-s', '--silent', help='silent mode', action='store_true')
    parser.add_argument('-V', '--version', help='show version', action='version', version=__version__)
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


if __name__ == '__main__':
    main()
