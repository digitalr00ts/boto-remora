import logging
from functools import partial
from typing import FrozenSet

import boto3
import botocore

_LOGGER = logging.getLogger(__name__)


def is_region_accessible(region, session):
    """
    Checks region is accessible from a given session.
    see: https://www.cloudar.be/awsblog/checking-if-a-region-is-enabled-using-the-aws-api/
    """
    client = session.client("sts", region_name=region)
    try:
        client.get_caller_identity()
    except botocore.exceptions.ClientError:
        _LOGGER.debug("Unable to access region %s.", region)
        return False
    return True


def get_accessible_regions(service_name: str, session: boto3.session.Session) -> FrozenSet[str]:
    """ Returns enabled regions from a given session. """
    # TODO: Add partition
    regions = session.get_available_regions(service_name)
    is_region_accessible_ = partial(is_region_accessible, session=session)
    available_regions = frozenset(filter(is_region_accessible_, regions))

    if not available_regions:
        _LOGGER.error(
            "Access to all regions failed. Credentials may be invalid or there is a network issue."
        )

    return available_regions
