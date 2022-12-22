import argparse
import logging

import tomli

try:
    from mastodon_telegram_bridge._version import __version__
except ImportError:
    __version__ = 'unknown'
from mastodon_telegram_bridge.bridge import Bridge


def main():
    parser = argparse.ArgumentParser('mastodon-telegram-bridge',
                                     description=f'A simple telegram bot bridges mastodon timeline. {__version__}')
    parser.add_argument('config', help='config file path', nargs='?', default='config.toml')
    parser.add_argument('-v', '--verbose', help='verbose mode', action='store_true')
    parser.add_argument('-d', '--debug', help='debug mode', action='store_true')
    parser.add_argument('-V', '--version', help='show version', action='version', version=__version__)
    args = parser.parse_args()
    if args.verbose:
        level = logging.INFO
    elif args.debug:
        level = logging.DEBUG
    else:
        level = logging.WARNING

    logging.basicConfig(level=level,
                        format='%(asctime)s: %(levelname)s %(name)s | %(message)s',
                        handlers=[logging.StreamHandler()])
    with open(args.config, 'rb') as cfg:
        config = tomli.load(cfg)
    Bridge(**config).run()


if __name__ == '__main__':
    main()
