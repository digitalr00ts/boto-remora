""" Main objects and functions for boto_remora.pricing """
import dataclasses
import logging
from collections import Mapping, defaultdict, deque
from itertools import chain
from typing import Any, Dict, Optional, Sequence, Tuple, Union

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
    currency: str = "USD"
    aws_pricing: Pricing = dataclasses.field(default=Pricing(), repr=False)
    resource_key: Optional[ResourceKey] = dataclasses.field(default=None, init=False, repr=False)
    _data: Dict[str, Dict[str, Sequence[Offer]]] = dataclasses.field(
        default_factory=dict, repr=False, init=False
    )
    _keys: Sequence[str] = dataclasses.field(default_factory=tuple, repr=False, init=False)
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

    @property
    def available_keys(self):
        """ Possible values for attributes """
        if not self._keys:
            pages = self.aws_pricing.client.get_paginator("get_attribute_values").paginate(
                ServiceCode=getattr(self.resource_key, "servicecode"),
                AttributeName=getattr(self.resource_key, "key"),
            )
            results = chain.from_iterable(
                map(lambda item_: (val_["Value"] for val_ in item_["AttributeValues"]), pages)
            )
            self._keys = tuple(results)
        return self._keys

    @property
    def cached(self) -> Sequence[Offer]:
        """ All cached data """
        return self._flatten(self._data)

    def _flatten(self, data: Mapping) -> Sequence[Any]:
        """ Flatten cached data """
        rtn = deque()
        for val_ in data.values():
            rtn.extend(self._flatten(val_)) if isinstance(val_, Mapping) else rtn.extend(val_)
        return rtn

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
        offer_kargs["region"] = self.aws_pricing.region_names_rev[
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

        return self.aws_pricing.get_price_list(
            servicecode=self.resource_key.servicecode, region=region, filter_kv=filter_kv,
        )

    def get(self, region: str, key: str,) -> Sequence[Offer]:
        """ Lazily load and return list of offers from region.key. """
        if not (self._data.get(region) and self._data[region].get(key)):
            self._data[region][key] = list(
                map(
                    self._create_offer_from_pricelist_item,
                    self.get_pricelist_raw(region=region, val_for_key=key),
                )
            )

        return self._data[region][key]

    def filter_cached(
        self,
        filters: Optional[Union[Sequence[Sequence[str]], Dict[str, str]]] = None,
        region: Optional[str] = None,
        key: Optional[str] = None,
    ) -> Sequence[Offer]:
        """ Filter cached offers """

        def isdata(offer: Offer) -> bool:
            attribs = offer.attributes
            filter_vals = map(lambda fil_: attribs.get(fil_[0]) == fil_[1], filters)
            return all(filter_vals) if attribs else False

        filters = deque(filters.items()) if isinstance(filters, Mapping) else deque(filters)

        if region and key:
            data = self.get(region=region, key=key)
        elif region:
            data = self._data[region]
        elif key:
            filters.append((self.resource_key, key))
            data = self.cached
        else:
            data = self.cached

        _LOGGER.debug("Filter for offers %s", filters)
        return tuple(filter(isdata, data))

    def get_ece2filtered(
        self,
        region: str,
        key: str,
        os: str = "Linux",
        sw: str = "NA",
        capstat: str = "Used",
        tenancy: str = "Shared",
        license: str = "No License required",
    ) -> Sequence[Offer]:
        """ EC2 specific filtering of cached offers """
        filters = deque()
        if os:
            filters.append(("operatingSystem", os))
        if sw:
            filters.append(("preInstalledSw", sw))
        if capstat:
            filters.append(("capacitystatus", capstat))
        if tenancy:
            filters.append(("tenancy", tenancy))
        if license:
            filters.append(("licenseModel", license))

        return self.filter_cached(filters=filters, region=region, key=key)
