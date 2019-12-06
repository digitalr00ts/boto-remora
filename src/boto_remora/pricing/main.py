""" Main objects and functions for boto_remora.pricing """
import dataclasses
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

from boto_remora.aws import Pricing
from boto_remora.util import ExtendedEnum


_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class ResourceKey:
    """ Describes AWS resource """

    __slots__ = ["servicecode", "productFamily", "key"]
    servicecode: str
    productFamily: str  # pylint: disable=invalid-name
    key: str


class AWSResourceKeys(ExtendedEnum):
    """ ResourceKey objects for AWS resources """

    EC2 = ResourceKey("AmazonEC2", "Compute Instance", "instanceType")
    EBS = ResourceKey("AmazonEC2", "Storage", "volumeType")


@dataclasses.dataclass()  # pylint: disable=too-many-instance-attributes
class Offer:
    """ AWS Pricing API response """

    unit: str
    description: str
    attributes: Dict[str, str] = dataclasses.field(default_factory=dict)
    productFamily: str = ""  # pylint: disable=invalid-name
    currency: str = "USD"
    prices: Union[Dict[str, float], float] = None
    region: Optional[str] = None
    serviceCode: str = ""  # pylint: disable=invalid-name
    terms: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass()
class Offers:
    """
    A collection of offers
    """

    resource_type: str
    remora_aws: Pricing
    currency: str = "USD"
    resource_key: Optional[ResourceKey] = dataclasses.field(default=None, init=False)
    _data: Dict[str, Dict[str, List[Offer]]] = dataclasses.field(
        default_factory=list, repr=False, init=False
    )
    # provison_type: str = "OnDemand"

    def __post_init__(self):
        self.resource_key = getattr(AWSResourceKeys, self.resource_type).value
        _LOGGER.debug(self.resource_key)
        self._data = defaultdict(dict)

    @property
    def offers(self):
        """

        Returns
        -------
        List of Offer objects
        """
        return list(self._data)

    def _create_offer_from_pricelist_item(self, pricelist_item):
        product = pricelist_item["product"]
        terms = pricelist_item["terms"]

        prices = dict()
        pdetails = dict()
        # TODO: changing to recursion for more robust solution
        for ptype, v1 in terms.items():  # pylint: disable = invalid-name
            for v2 in v1.values():  # pylint: disable = invalid-name
                for pdetails in v2["priceDimensions"].values():
                    prices[ptype] = float(pdetails["pricePerUnit"][self.currency])

        offer_kargs = dict()
        offer_kargs["attributes"] = product["attributes"]
        offer_kargs["productFamily"] = product["productFamily"]
        offer_kargs["currency"] = self.currency
        offer_kargs["serviceCode"] = pricelist_item["serviceCode"]
        offer_kargs["region"] = self.remora_aws.region_names_rev[
            product["attributes"]["location"]
        ]
        offer_kargs["prices"] = prices
        offer_kargs["unit"] = pdetails["unit"]
        offer_kargs["description"] = pdetails["description"]
        offer_kargs["terms"] = terms

        return Offer(**offer_kargs)

    def get_pricelist_raw(
        self,
        region: Optional[str] = None,
        val_for_key: Optional[str] = None,
        key_val: Dict[str, Union[bool, int, str]] = None,
    ):
        """ Get list of prices as returned by the AWS API """
        filter_kv = key_val.copy() if key_val else dict()
        pfkey = "productFamily"
        filter_kv[pfkey] = getattr(self.resource_key, pfkey)
        if val_for_key:
            filter_kv[self.resource_key.key] = val_for_key

        return self.remora_aws.get_price_list(
            servicecode=self.resource_key.servicecode, region=region, filter_kv=filter_kv,
        )

    def get_offers(self, region: str, key: str) -> List[Offer]:
        """ Get list of offers from region.key. """
        if not (self._data.get(region) and self._data[region].get(key)):
            self._data[region][key] = list(
                map(
                    self._create_offer_from_pricelist_item,
                    self.get_pricelist_raw(region=region, val_for_key=key),
                )
            )

        return self._data[region][key]
