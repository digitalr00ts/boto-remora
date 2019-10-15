""" Exceptions module """


class BotoRemoraError(Exception):
    """ Base Exception for AWS Pricing """

    fmt = "{}"

    def __init__(self, *args, **kwargs):
        msg = self.fmt.format(*args, **kwargs)
        super().__init__(self, msg)


class BotoRemoraInvalidServiceRegion(BotoRemoraError, TypeError):
    """ Exception for attempting to a region without the pricing endpoint """

    fmt = "Service {} is not available in region {}."


class BotoRemoraPricingResourceKeyUndefined(BotoRemoraError, KeyError):
    """ Exception for attempting to a region without the pricing endpoint """

    fmt = "{} is not a defined ResourceKey."
