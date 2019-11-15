""" boto_remora.aws package """
import dataclasses
import logging

from typing import Iterable, List, Optional

import boto3
import botocore

from . import helper

from boto_remora.exception import (
    BotoRemoraInvalidServiceRegion, BotoRemoraPricingResourceKeyUndefined
)


_LOGGER = logging.getLogger(__name__)


class ResourceKeys(dict):
    """ Dict for custom error. """

    def __getitem__(self, key):
        if key not in self:
            raise BotoRemoraPricingResourceKeyUndefined(key)

        return super().__getitem__(key)


@dataclasses.dataclass(eq=False)
class AwsBase:
    """ Base class to use AWS API. """

    profile_name: Optional[str] = None
    region_name: Optional[str] = None  # TODO: Read in defaults from boto
    session: Optional[boto3.session.Session] = dataclasses.field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self):
        if not self.session:
            self.session = boto3.Session(
                region_name=self.region_name, profile_name=self.profile_name
            )
        if not self.profile_name:
            self.profile_name = self.session.profile_name
        if not self.region_name:
            self.region_name = self.session.region_name

    def is_profile_available(self, profile=None):
        if profile is None:
            profile = self.session.profile_name
        if profile in self.session.available_profiles:
            return True
        _LOGGER.warning("Profile %s was not found.", self.profile_name)
        return False


@dataclasses.dataclass(eq=False)
class AwsBaseService(AwsBase):
    """ Base class to call a service with AWS API. """

    service_name: str = ""
    filter_keys: List[str] = dataclasses.field(
        default_factory=lambda: ["Name", "Value"]
    )
    client: Optional[object] = dataclasses.field(
        default=None, init=False, compare=False, repr=False
    )
    _available_regions: Optional[Iterable[str]] = dataclasses.field(
        default=None, init=False, repr=False
    )

    def __post_init__(self):
        super().__post_init__()
        if not self.region_name:
            self.region_name = self.session.region_name
        if self.region_name not in self.session.get_available_regions(
            self.service_name
        ):
            raise BotoRemoraInvalidServiceRegion(self.service_name, self.region_name)
        self.client = self.session.client(self.service_name)

    @property
    def available_regions(self):
        """ Checks to which regions are enabled and accessible """
        if not self._available_regions:
            self._available_regions = helper.get_accessible_regions(
                self.service_name, self.session
            )

        return self._available_regions

    # def filter_fmt(self, filters: Dict):
    #     """ Returns list formated for filter. """
    #     return [
    #         {self.filter_keys[0]: k, self.filter_keys[1]: v} for k, v in filters.items()
    #     ]
