import unittest

from pydantic import ValidationError

from common.models.agoge import CloudEnvModel
from common.models.wireguard import (
    WireGuardEndpointRecordModel,
    WireGuardPublicEndpointModel,
)


class WireGuardEndpointModelsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.record = WireGuardEndpointRecordModel(
            id="12345",
            hostname="WG-12345.VPN.EXAMPLE.EDU",
            server_name="unit-abc-wireguard",
            port=51820,
            external_ip_name="unit-abc-wireguard-ip",
            public_ip="203.0.113.10",
            status="active",
            unit_id="unit-abc",
            created_timestamp=1.0,
            updated_timestamp=2.0,
        )

    def test_hostname_is_normalized_to_an_absolute_dns_name(self) -> None:
        self.assertEqual(self.record.hostname, "wg-12345.vpn.example.edu.")

    def test_public_response_does_not_expose_internal_mapping_or_ip(self) -> None:
        response = WireGuardPublicEndpointModel.from_record(self.record).model_dump()

        self.assertEqual(
            response,
            {
                "id": "12345",
                "hostname": "wg-12345.vpn.example.edu.",
                "port": 51820,
                "status": "active",
            },
        )
        self.assertNotIn("unit_id", response)
        self.assertNotIn("server_name", response)
        self.assertNotIn("public_ip", response)

    def test_peer_id_must_be_five_digits_and_cannot_start_with_zero(self) -> None:
        invalid_record = self.record.model_dump() | {"id": "01234"}

        with self.assertRaises(ValidationError):
            WireGuardEndpointRecordModel.model_validate(invalid_record)

    def test_project_dns_settings_fit_the_generated_label_and_parent_zone(self) -> None:
        valid = CloudEnvModel.model_validate({
            "wireguard_dns_prefix": "a" * 57,
            "wireguard_dns_suffix": ".vpn.example.edu.",
            "parent_dns_suffix": ".example.edu.",
        })
        self.assertEqual(valid.wireguard_dns_prefix, "a" * 57)

        with self.assertRaisesRegex(ValidationError, "at most 57"):
            CloudEnvModel.model_validate({"wireguard_dns_prefix": "a" * 58})

        with self.assertRaisesRegex(ValidationError, "subdomain"):
            CloudEnvModel.model_validate({
                "wireguard_dns_suffix": ".vpn.other.example.",
                "parent_dns_suffix": ".example.edu.",
            })

    def test_project_wireguard_port_rejects_booleans_and_normalizes_digits(self) -> None:
        self.assertEqual(
            CloudEnvModel.model_validate({'wireguard_port': '41194'}).wireguard_port,
            41194,
        )
        for invalid in (True, False, 1.5, '1.5', 'not-a-port'):
            with self.subTest(value=invalid), self.assertRaises(ValidationError):
                CloudEnvModel.model_validate({'wireguard_port': invalid})


if __name__ == "__main__":
    unittest.main()
