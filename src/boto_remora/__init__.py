""" c7n Broom top level """
import logging

import pkg_resources

from . import aws, pricing


try:
    __version__ = pkg_resources.get_distribution(__name__).version
except pkg_resources.DistributionNotFound:
    __version__ = ""


logging.getLogger(__name__).addHandler(logging.NullHandler())
logging.getLogger("botocore").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

__all__ = ["aws", "pricing"]
