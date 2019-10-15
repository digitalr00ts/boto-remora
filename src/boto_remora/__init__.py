""" c7n Broom top level """
import logging

import pkg_resources

from . import aws, pricing


try:
    __version__ = pkg_resources.get_distribution(__name__).version
except pkg_resources.DistributionNotFound:
    __version__ = ""


__all__ = ["aws", "pricing"]

logging.getLogger(__name__).addHandler(logging.NullHandler())
