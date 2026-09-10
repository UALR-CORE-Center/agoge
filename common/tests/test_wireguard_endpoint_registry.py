import unittest

from common.constants.database import DbOperators
from common.exceptions import BadRequest, NotFound
from common.models.wireguard import WireGuardPublicEndpointModel
from common.services.wireguard_endpoint import Conflict, WireGuardEndpointRegistry


class _FakeDocument:
    def __init__(self, records: dict, document_id: str):
        self.records = records
        self.document_id = document_id

    def create(self, data: dict) -> None:
        if self.document_id in self.records:
            raise Conflict("document already exists")
        self.records[self.document_id] = dict(data)

    def get(self, transaction=None):
        return _FakeSnapshot(self.records.get(self.document_id))


class _FakeSnapshot:
    def __init__(self, data):
        self.data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self.data)


class _FakeCollection:
    def __init__(self, records: dict):
        self.records = records

    def document(self, document_id: str) -> _FakeDocument:
        return _FakeDocument(self.records, document_id)


class _FakeFirestoreClient:
    def __init__(self, collections: dict):
        self.collections = collections

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self.collections.setdefault(name, {}))


class _FakeTransaction:
    def set(self, document: _FakeDocument, data: dict, merge: bool = False):
        if merge:
            document.records[document.document_id].update(data)
        else:
            document.records[document.document_id] = dict(data)

    def delete(self, document: _FakeDocument):
        document.records.pop(document.document_id, None)


class _FakeDatabase:
    def __init__(self):
        self.collections: dict[str, dict[str, dict]] = {
            "wireguard-endpoint": {},
            "wireguard-endpoint-claim": {},
        }
        self.db = _FakeFirestoreClient(self.collections)
        self.hide_query_results = False

    @property
    def records(self):
        return self.collections["wireguard-endpoint"]

    @property
    def claims(self):
        return self.collections["wireguard-endpoint-claim"]

    def query(self, collection_name, filters=None):
        if self.hide_query_results:
            return []
        records = list(self.collections[collection_name.value].values())
        for field, operator, value in filters or []:
            if operator == DbOperators.EQUAL:
                records = [record for record in records if record.get(field) == value]
            elif operator == DbOperators.LESS_THAN_EQ:
                records = [
                    record
                    for record in records
                    if record.get(field) is not None and record.get(field) <= value
                ]
            else:
                raise AssertionError(f"Unsupported fake operator: {operator}")
        return records

    def get(self, collection_name, doc_id):
        return dict(self.collections[collection_name.value].get(doc_id, {}))

    def update(self, collection_name, doc_id, data):
        self.collections[collection_name.value][doc_id].update(data)

    def delete(self, collection_name, doc_id):
        self.collections[collection_name.value].pop(doc_id, None)

    def transaction(self, operation_func, *args, **kwargs):
        return operation_func(_FakeTransaction(), *args, **kwargs)


class WireGuardEndpointRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _FakeDatabase()
        self.env = {
            "project": "agoge-class-a",
            "wireguard_dns_prefix": "wg",
            "wireguard_dns_suffix": ".gateways.example.edu.",
            "parent_dns_suffix": ".example.edu.",
        }
        self.now = 1_000_000.0

    def registry(self, ids) -> WireGuardEndpointRegistry:
        candidates = iter(ids)
        return WireGuardEndpointRegistry(
            env_dict=self.env,
            db=self.db,
            peer_id_factory=lambda: next(candidates),
            timestamp_factory=lambda: self.now,
        )

    def test_allocate_reserves_atomic_document_and_fqdn(self) -> None:
        endpoint = self.registry(["12345"]).allocate(
            unit_id="abcdefghij",
            server_name="abcdefghij-wireguard",
            external_ip_name="abcdefghij-wireguard-ip",
            expires=2_000_000_000,
        )

        self.assertEqual(endpoint.id, "12345")
        self.assertEqual(
            endpoint.hostname,
            "wg-12345.agoge-class-a.gateways.example.edu.",
        )
        self.assertEqual(self.db.records["12345"]["unit_id"], "abcdefghij")
        self.assertEqual(self.db.records["12345"]["status"], "reserved")
        self.assertEqual(self.db.claims["abcdefghij"]["endpoint_id"], "12345")

    def test_allocate_retries_a_create_collision(self) -> None:
        first = self.registry(["12345"]).allocate("firstunitx", "firstunitx-wireguard")
        second = self.registry(["12345", "23456"]).allocate("secondunit", "secondunit-wireguard")

        self.assertEqual(first.id, "12345")
        self.assertEqual(second.id, "23456")
        self.assertEqual(len(self.db.records), 2)

    def test_allocate_is_idempotent_for_a_unit(self) -> None:
        registry = self.registry(["34567"])
        first = registry.allocate("abcdefghij", "abcdefghij-wireguard")
        second = registry.allocate("abcdefghij", "ignored-server")

        self.assertEqual(second.id, first.id)
        self.assertEqual(len(self.db.records), 1)

    def test_cancel_reservation_atomically_removes_owned_claim_and_endpoint(self) -> None:
        registry = self.registry(["34987"])
        registry.allocate("abcdefghij", "abcdefghij-wireguard")

        with self.assertRaisesRegex(BadRequest, "does not belong"):
            registry.cancel_reservation("34987", unit_id="otherunitx")
        self.assertIn("34987", self.db.records)
        self.assertIn("abcdefghij", self.db.claims)

        registry.cancel_reservation("34987", unit_id="abcdefghij")
        self.assertNotIn("34987", self.db.records)
        self.assertNotIn("abcdefghij", self.db.claims)

    def test_stale_same_unit_contenders_converge_on_one_transactional_claim(self) -> None:
        # Simulate two allocators whose preflight query saw the same stale empty
        # result. The claim document is the transactionally serialized source of
        # truth, so the second random candidate must not be created.
        self.db.hide_query_results = True
        first = self.registry(["35678"]).allocate("abcdefghij", "abcdefghij-wireguard")
        second = self.registry(["36789"]).allocate("abcdefghij", "abcdefghij-wireguard")

        self.assertEqual(first.id, "35678")
        self.assertEqual(second.id, "35678")
        self.assertEqual(set(self.db.records), {"35678"})
        self.assertEqual(
            self.db.claims["abcdefghij"]["endpoint_id"],
            "35678",
        )

    def test_public_projection_does_not_expose_private_metadata(self) -> None:
        registry = self.registry(["45678"])
        registry.allocate("abcdefghij", "abcdefghij-wireguard", "abcdefghij-wireguard-ip")
        registry.activate("45678", unit_id="abcdefghij", public_ip="203.0.113.10")

        response = WireGuardPublicEndpointModel.from_record(
            registry.get("45678", public_only=True)
        ).model_dump()

        self.assertEqual(set(response), {"id", "hostname", "port", "status"})
        self.assertNotIn("public_ip", response)
        self.assertNotIn("unit_id", response)
        self.assertNotIn("server_name", response)

    def test_reserved_endpoint_is_not_public_until_activated(self) -> None:
        registry = self.registry(["46789"])
        registry.allocate("abcdefghij", "abcdefghij-wireguard")

        with self.assertRaises(NotFound):
            registry.get("46789", public_only=True)

        registry.stage("46789", unit_id="abcdefghij", public_ip="203.0.113.10")
        with self.assertRaises(NotFound):
            registry.get("46789", public_only=True)

        registry.activate("46789", unit_id="abcdefghij")
        self.assertEqual(registry.get("46789", public_only=True).status, "active")

    def test_late_build_stage_cannot_demote_an_active_endpoint(self) -> None:
        registry = self.registry(["47891"])
        registry.allocate("abcdefghij", "abcdefghij-wireguard")
        registry.activate("47891", unit_id="abcdefghij", public_ip="203.0.113.10")

        staged = registry.stage(
            "47891",
            unit_id="abcdefghij",
            public_ip="203.0.113.10",
        )

        self.assertEqual(staged.status, "active")
        self.assertEqual(self.db.records["47891"]["status"], "active")

    def test_released_endpoint_is_tombstoned_and_not_public(self) -> None:
        registry = self.registry(["56789"])
        registry.allocate("abcdefghij", "abcdefghij-wireguard")
        registry.mark_releasing("56789", unit_id="abcdefghij")
        registry.release("56789", unit_id="abcdefghij")

        self.assertEqual(self.db.records["56789"]["status"], "released")
        with self.assertRaises(NotFound):
            registry.get("56789", public_only=True)

        with self.assertRaisesRegex(BadRequest, "still quarantined"):
            registry.purge("56789", unit_id="abcdefghij", now=self.now)

        registry.purge(
            "56789",
            unit_id="abcdefghij",
            now=self.now + registry.TOMBSTONE_RETENTION_SECONDS,
        )
        self.assertNotIn("56789", self.db.records)
        self.assertNotIn("abcdefghij", self.db.claims)

    def test_delayed_events_cannot_revive_releasing_or_released_endpoint(self) -> None:
        registry = self.registry(["67891"])
        registry.allocate("abcdefghij", "abcdefghij-wireguard")
        registry.activate("67891", unit_id="abcdefghij", public_ip="203.0.113.10")
        registry.mark_releasing("67891", unit_id="abcdefghij")

        with self.assertRaisesRegex(BadRequest, "releasing.*activated"):
            registry.activate("67891", unit_id="abcdefghij", public_ip="203.0.113.11")
        with self.assertRaisesRegex(BadRequest, "releasing.*staged"):
            registry.stage("67891", unit_id="abcdefghij", public_ip="203.0.113.11")
        registry.mark_reserved("67891", unit_id="abcdefghij")
        registry.mark_error("67891", unit_id="abcdefghij")
        self.assertEqual(self.db.records["67891"]["status"], "releasing")
        self.assertEqual(self.db.records["67891"]["public_ip"], "203.0.113.10")

        registry.release("67891", unit_id="abcdefghij")
        released_at = self.db.records["67891"]["released_timestamp"]
        self.now += 60
        with self.assertRaisesRegex(BadRequest, "released.*activated"):
            registry.activate("67891", unit_id="abcdefghij", public_ip="203.0.113.12")
        with self.assertRaisesRegex(BadRequest, "released.*staged"):
            registry.stage("67891", unit_id="abcdefghij", public_ip="203.0.113.12")
        registry.mark_reserved("67891", unit_id="abcdefghij")
        registry.mark_error("67891", unit_id="abcdefghij")
        registry.mark_releasing("67891", unit_id="abcdefghij")
        registry.release("67891", unit_id="abcdefghij")

        self.assertEqual(self.db.records["67891"]["status"], "released")
        self.assertIsNone(self.db.records["67891"]["public_ip"])
        self.assertEqual(self.db.records["67891"]["released_timestamp"], released_at)

    def test_same_owner_provisioning_guard_rejects_releasing_and_released(self) -> None:
        registry = self.registry(["67912"])
        registry.allocate("abcdefghij", "abcdefghij-wireguard")
        endpoint = registry.require_provisionable("67912", unit_id="abcdefghij")
        self.assertEqual(endpoint.status, "reserved")

        registry.mark_releasing("67912", unit_id="abcdefghij")
        with self.assertRaisesRegex(BadRequest, "releasing.*cannot be provisioned"):
            registry.require_provisionable("67912", unit_id="abcdefghij")

        registry.release("67912", unit_id="abcdefghij")
        with self.assertRaisesRegex(BadRequest, "released.*cannot be provisioned"):
            registry.require_provisionable("67912", unit_id="abcdefghij")

    def test_reused_id_rejects_every_delayed_transition_from_old_owner(self) -> None:
        endpoint_id = "68912"
        registry = self.registry([endpoint_id])
        registry.allocate("oldunitxx", "oldunitxx-wireguard")
        registry.stage(
            endpoint_id,
            unit_id="oldunitxx",
            public_ip="203.0.113.10",
        )
        registry.mark_releasing(endpoint_id, unit_id="oldunitxx")
        registry.release(endpoint_id, unit_id="oldunitxx")
        registry.purge(
            endpoint_id,
            unit_id="oldunitxx",
            now=self.now + registry.TOMBSTONE_RETENTION_SECONDS,
        )

        new_owner_registry = self.registry([endpoint_id])
        new_owner_registry.allocate("newunitxx", "newunitxx-wireguard")
        new_owner_record = dict(self.db.records[endpoint_id])
        new_owner_claim = dict(self.db.claims["newunitxx"])

        delayed_old_owner_actions = {
            "stage": lambda: registry.stage(
                endpoint_id,
                unit_id="oldunitxx",
                public_ip="203.0.113.11",
            ),
            "activate": lambda: registry.activate(
                endpoint_id,
                unit_id="oldunitxx",
                public_ip="203.0.113.11",
            ),
            "mark_reserved": lambda: registry.mark_reserved(
                endpoint_id,
                unit_id="oldunitxx",
            ),
            "mark_error": lambda: registry.mark_error(
                endpoint_id,
                unit_id="oldunitxx",
            ),
            "mark_releasing": lambda: registry.mark_releasing(
                endpoint_id,
                unit_id="oldunitxx",
            ),
            "release": lambda: registry.release(
                endpoint_id,
                unit_id="oldunitxx",
            ),
        }
        for action_name, action in delayed_old_owner_actions.items():
            with self.subTest(action=action_name):
                with self.assertRaisesRegex(BadRequest, "does not belong"):
                    action()
                self.assertEqual(self.db.records[endpoint_id], new_owner_record)
                self.assertEqual(self.db.claims["newunitxx"], new_owner_claim)
                self.assertNotIn("oldunitxx", self.db.claims)

    def test_purge_released_only_removes_tombstones_older_than_24_hours(self) -> None:
        registry = self.registry(["71234", "72345"])
        registry.allocate("firstunitx", "firstunitx-wireguard")
        registry.release("71234", unit_id="firstunitx")

        self.now += registry.TOMBSTONE_RETENTION_SECONDS - 60
        registry.allocate("secondunit", "secondunit-wireguard")
        registry.release("72345", unit_id="secondunit")
        self.now += 120

        self.assertEqual(registry.purge_released(now=self.now), 1)
        self.assertNotIn("71234", self.db.records)
        self.assertIn("72345", self.db.records)
        self.assertNotIn("firstunitx", self.db.claims)
        self.assertIn("secondunit", self.db.claims)

    def test_wireguard_port_is_configurable_and_validated(self) -> None:
        self.env["wireguard_port"] = "41194"
        endpoint = self.registry(["81234"]).allocate("abcdefghij", "abcdefghij-wireguard")
        self.assertEqual(endpoint.port, 41194)

        for invalid_port in (0, 65536, "not-a-port", True):
            with self.subTest(port=invalid_port):
                self.db = _FakeDatabase()
                self.env["wireguard_port"] = invalid_port
                with self.assertRaisesRegex(BadRequest, "wireguard_port"):
                    self.registry(["82345"]).allocate("abcdefghij", "abcdefghij-wireguard")

    def test_dns_prefix_keeps_generated_label_within_63_characters(self) -> None:
        self.env["wireguard_dns_prefix"] = "a" * 57
        endpoint = self.registry(["83456"]).allocate("abcdefghij", "abcdefghij-wireguard")
        self.assertEqual(len(endpoint.hostname.split(".")[0]), 63)

        self.db = _FakeDatabase()
        self.env["wireguard_dns_prefix"] = "a" * 58
        with self.assertRaisesRegex(BadRequest, "at most 57"):
            self.registry(["84567"]).allocate("abcdefghij", "abcdefghij-wireguard")

    def test_dns_suffix_must_stay_in_the_parent_dns_namespace(self) -> None:
        self.env["wireguard_dns_suffix"] = ".nested.gateways.example.edu."
        endpoint = self.registry(["85678"]).allocate("abcdefghij", "abcdefghij-wireguard")
        self.assertEqual(
            endpoint.hostname,
            "wg-85678.agoge-class-a.nested.gateways.example.edu.",
        )

        for outside_suffix in ("example.com", "malicious-example.edu"):
            with self.subTest(suffix=outside_suffix):
                self.db = _FakeDatabase()
                self.env["wireguard_dns_suffix"] = outside_suffix
                with self.assertRaisesRegex(BadRequest, "subdomain"):
                    self.registry(["86789"]).allocate("abcdefghij", "abcdefghij-wireguard")

    def test_shared_parent_zone_namespaces_are_unique_per_gcp_project(self) -> None:
        first = self.registry(["91234"]).allocate("firstunitx", "firstunitx-wireguard")

        second_db = _FakeDatabase()
        second_env = dict(self.env, project="agoge-class-b")
        second = WireGuardEndpointRegistry(
            env_dict=second_env,
            db=second_db,
            peer_id_factory=lambda: "91234",
            timestamp_factory=lambda: self.now,
        ).allocate("secondunit", "secondunit-wireguard")

        self.assertNotEqual(first.hostname, second.hostname)
        self.assertEqual(
            second.hostname,
            "wg-91234.agoge-class-b.gateways.example.edu.",
        )

    def test_complete_project_qualified_hostname_must_fit_dns_limit(self) -> None:
        long_suffix = '.'.join(["a" * 63, "b" * 63, "c" * 63, "d" * 50])
        self.env["wireguard_dns_suffix"] = long_suffix
        self.env["parent_dns_suffix"] = long_suffix

        with self.assertRaisesRegex(BadRequest, "Invalid WireGuard DNS configuration"):
            self.registry(["93456"]).allocate("abcdefghij", "abcdefghij-wireguard")

    def test_project_is_required_for_a_collision_free_dns_pool(self) -> None:
        self.env.pop("project")
        with self.assertRaisesRegex(BadRequest, "immutable GCP project ID"):
            self.registry(["92345"]).allocate("abcdefghij", "abcdefghij-wireguard")

        for invalid_project in ("short", "UPPER-project", "project_underscore", "a" * 31):
            with self.subTest(project=invalid_project):
                self.db = _FakeDatabase()
                self.env["project"] = invalid_project
                with self.assertRaisesRegex(BadRequest, "immutable GCP project ID"):
                    self.registry(["92345"]).allocate(
                        "abcdefghij",
                        "abcdefghij-wireguard",
                    )


if __name__ == "__main__":
    unittest.main()
