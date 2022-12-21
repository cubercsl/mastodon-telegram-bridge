import argparse
import json
import logging

from mastodon_telegram_bridge.bridge import Bridge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='config file path', nargs='?', default='config.json')
    parser.add_argument('-v', '--verbose', help='verbose mode', action='store_true')
    parser.add_argument('-d', '--debug', help='debug mode', action='store_true')
    parser.add_argument('--disable-send-to-mastodon', help='disable sending messages to mastodon', action='store_true')
    parser.add_argument('--disable-send-to-telegram', help='disable sending messages to telegram', action='store_true')
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
    with open(args.config) as cfg:
        config = json.load(cfg)
    if args.disable_send_to_mastodon and args.disable_send_to_telegram:
        raise ValueError('Both --disable-send-to-mastodon and --disable-send-to-telegram are set, do nothing.')
    telegram_to_mastodon = True
    mastodon_to_telegram = True
    if args.disable_send_to_mastodon:
        telegram_to_mastodon = False
    if args.disable_send_to_telegram:
        mastodon_to_telegram = False
    Bridge(**config).run(telegram_to_mastodon=telegram_to_mastodon, mastodon_to_telegram=mastodon_to_telegram)


if __name__ == '__main__':
    main()
