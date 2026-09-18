from google.cloud.compute_v1 import Address


class AddressResource:
    """Builds regional Compute Engine external-address resources."""

    @staticmethod
    def new(
        name: str,
        description: str = None,
        network_tier: str = "PREMIUM",
    ) -> Address:
        if not description:
            description = f"Agoge reserved external address {name}"

        return Address(
            name=name,
            description=description,
            address_type="EXTERNAL",
            network_tier=network_tier,
        )
