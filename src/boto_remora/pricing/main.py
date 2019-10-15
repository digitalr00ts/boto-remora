""" Main objects and functions for boto_remora.pricing """
import dataclasses
import json
import logging

from collections import defaultdict
from typing import Dict, List, Optional, Union

from boto_remora.aws import Pricing


_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class ResourceKey:
    """ Describes AWS resource """

    __slots__ = ["servicecode", "productFamily", "unique_key"]
    servicecode: str
    productFamily: str  # pylint: disable=invalid-name
    unique_key: str


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


@dataclasses.dataclass()
class Offers:
    """
    A collection of offers
    """

    resource_type: str
    aws_client: Pricing
    currency: str = "USD"
    resource_key: Optional[ResourceKey] = dataclasses.field(default=None, init=False)
    _data: List[Offer] = dataclasses.field(default_factory=list, repr=False, init=False)
    # provison_type: str = "OnDemand"

    def __post_init__(self):
        self.resource_key = AWS_RESOURCE_KEYS[self.resource_type]
        self._data = self._populate()

    # def __len__(self):
    #     return len(self._data)

    @property
    def offers(self):
        """

        Returns
        -------
        List of Offer objects
        """
        return list(self._data)

    def _populate(self, region: Optional[str] = None):
        """
        Fetch from price API
        """
        key: str = "productFamily"
        filter_kv: Dict[str, str] = {key: getattr(self.resource_key, key, "")}
        if region:
            filter_kv["region"] = region

        response = self.aws_client.get_price_list(
            servicecode=self.resource_key.servicecode, filter_kv=filter_kv
        )

        return [
            self._create_offer_from_pricelist_item(pricelist_item)
            for pricelist_item in response
        ]

    def _create_offer_from_pricelist_item(self, pricelist_item):
        if isinstance(pricelist_item, str):
            pricelist_item = json.loads(pricelist_item)
        product = pricelist_item["product"]
        terms = pricelist_item["terms"]

        prices = dict()
        pdetails = dict()
        # TODO: changing to recursion for more robust solution
        for ptype, v1 in terms.items():  # pylint: disable = invalid-name
            for v2 in v1.values():  # pylint: disable = invalid-name
                for pdetails in v2["priceDimensions"].values():
                    prices[ptype] = pdetails["pricePerUnit"][self.currency]

        offer_kargs = dict()
        offer_kargs["attributes"] = product["attributes"]
        offer_kargs["productFamily"] = product["productFamily"]
        offer_kargs["currency"] = self.currency
        offer_kargs["serviceCode"] = pricelist_item["serviceCode"]
        offer_kargs["region"] = self.aws_client.region_map_rev[
            product["attributes"]["location"]
        ]
        offer_kargs["prices"] = prices
        offer_kargs["unit"] = pdetails["unit"]
        offer_kargs["description"] = pdetails["description"]

        return Offer(**offer_kargs)

    def prices_by_key(self, provision_type="OnDemand"):
        """

        Parameters
        ----------
        provision_type

        Returns
        -------

        """

        data = defaultdict(dict)
        for offer in self._data:
            data[offer.region].update(
                {
                    offer.attributes[self.resource_key.unique_key]: offer.prices[
                        provision_type
                    ]
                }
            )
        return dict(data)


AWS_RESOURCE_KEYS = {
    "EC2": ResourceKey("AmazonEC2", "Compute Instance", "instanceType"),
    "EBS": ResourceKey("AmazonEC2", "Storage", "volumeType"),
}
