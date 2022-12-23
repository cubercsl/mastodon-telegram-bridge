import argparse

import betterlogging as logging
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
        config = tomli.load(cfg)
    bridge = Bridge(**config)
    if not args.dry_run:
        bridge.run()
    else:
        logging.info('dry run, exit')


if __name__ == '__main__':
    main()
