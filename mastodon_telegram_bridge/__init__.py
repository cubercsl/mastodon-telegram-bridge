from ._version import __version__
from .bridge import Bridge
from .cli import main
from .filter import Filter
from .footer import Footer
from .typing import BridgeOptionsDict, ConfigDict, MastodonToTelegramOptionsDict, OptionsDict, TelegramToMastodonOptionsDict

__author__ = "cubercsl <hi@cubercsl.site>"
__license__ = "MIT"
__version__ = __version__
__all__ = [
    'main',
    'Bridge',
    'Filter',
    'Footer',
    'ConfigDict',
    'OptionsDict',
    'BridgeOptionsDict',
    'MastodonToTelegramOptionsDict',
    'TelegramToMastodonOptionsDict',
]
