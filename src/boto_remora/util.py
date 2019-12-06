""" Helpers """

import logging
from enum import Enum


_LOGGER = logging.getLogger(__name__)


class ExtendedEnum(Enum):
    """ Add helper methods to Enums """

    @classmethod
    def values(cls):
        """ Returns iterator of all values """
        return map(lambda item: item.value, cls)
