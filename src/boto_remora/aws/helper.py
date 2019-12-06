""" Helper funtions for boto_remora.aws """
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from itertools import compress
from typing import FrozenSet, Iterator, Tuple

import boto3
import botocore

from boto_remora.aws.base import Sts


_LOGGER = logging.getLogger(__name__)


def is_region_accessible(region, session):
    """
    Checks region is accessible from a given session.
    see: https://www.cloudar.be/awsblog/checking-if-a-region-is-enabled-using-the-aws-api/
    """
    client = session.client("sts", region_name=region)
    try:
        client.get_caller_identity()
    except botocore.exceptions.ClientError as err:
        _LOGGER.debug(
            "%snable to access region %s.",
            f"Profile {session.profile_name} is u" if session.profile_name else "U",
            region,
        )
        # https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html#ErrorCodeList
        if err.response["Error"]["Code"] == "ExpiredToken":
            raise err from None
        _LOGGER.debug(err)
        return False
    return True


def get_accessible_regions(service_name: str, session: boto3.session.Session) -> FrozenSet[str]:
    """ Returns enabled regions from a given session. """
    # TODO: Add partition
    regions = session.get_available_regions(service_name)
    is_region_accessible_ = partial(is_region_accessible, session=session)
    available_regions = frozenset(filter(is_region_accessible_, regions))

    if not available_regions:
        _LOGGER.error("Access to all regions failed. There may be a network issue.")

    return available_regions


def get_authed_profiles(
    profiles: Iterator[str] = tuple(botocore.session.Session().available_profiles), region=None
) -> Tuple[str]:
    """ Return iterator of authenticated profiles. """
    kwargs = {"region_name": region} if region else dict()
    with ThreadPoolExecutor() as executor:
        account_check = executor.map(
            lambda profile_: Sts(profile_, **kwargs).is_session_region_accessible, profiles,
        )
        rtn = tuple(compress(profiles, account_check))
    return rtn
