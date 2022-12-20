import argparse
import json
import logging

from mastodon_telegram_bridge.bridge import Bridge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='config file path', nargs='?', default='config.json')
    parser.add_argument('-v', '--verbose', help='verbose mode', action='store_true')
    parser.add_argument('-d', '--debug', help='debug mode', action='store_true')
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
    Bridge(**config).run()


if __name__ == '__main__':
    main()
