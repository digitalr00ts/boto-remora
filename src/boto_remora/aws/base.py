""" boto_remora.aws package """
import dataclasses
import logging

from typing import Iterable, List, Optional

import boto3
import botocore

from boto_remora.exception import (
    BotoRemoraInvalidServiceRegion,
    BotoRemoraPricingResourceKeyUndefined,
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
        """
        Checks to which regions are enabled and accssible
        from: https://www.cloudar.be/awsblog/checking-if-a-region-is-enabled-using-the-aws-api/
        """
        if self._available_regions:
            return self._available_regions

        # TODO: Move this into a Sts object.
        ret_regions: List[str] = list()
        regions = self.session.get_available_regions()

        for region in regions:
            client = self.session.client("sts", region_name=region)
            try:
                client.get_caller_identity()
            except botocore.exceptions.ClientError:
                _LOGGER.debug("Unable to access region %s.", region)
            else:
                ret_regions.append(region)

        if not ret_regions:
            _LOGGER.error(
                "Access to all regions failed. Credentials may be invalid or there is a network issue."
            )

        return frozenset(ret_regions)

    # def filter_fmt(self, filters: Dict):
    #     """ Returns list formated for filter. """
    #     return [
    #         {self.filter_keys[0]: k, self.filter_keys[1]: v} for k, v in filters.items()
    #     ]
