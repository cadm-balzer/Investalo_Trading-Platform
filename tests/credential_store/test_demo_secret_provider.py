"""Actual AES-GCM; synthetic secrets/readers, private registry, no DB/native HTTP."""
from dataclasses import replace
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_bitget.futures_demo_read import DemoReadClient
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox
from investalo_bitget.signing import Credentials
from investalo_credential_store.bitget_payload import encode_credentials
from investalo_credential_store.demo_secret_provider import (
    DemoSecretSpec, DemoSecretRejected, DemoSecretSnapshot, SealedDemoReadProvider,
    seal_demo_secret, open_demo_secret, rewrap_demo_secret,
)
from investalo_credentials import (
    AADBinding, Envelope, EnvelopeRejected, KEKRing, dump_envelope, load_envelope, seal, open_envelope,
)
from test_futures_demo import AT, BINDING, OWNER, OTHER, response
from test_futures_demo_account import cohort, expectation

KEY1, KEY2 = bytes(range(32)), bytes(range(32, 64))
TRIPLE = Credentials("synthetic-demo-key", "synthetic-demo-secret", "synthetic-demo-pass")


def spec(**changes):
    return DemoSecretSpec(**{"binding": BINDING, "parent_uid": "0", "egress_ip": "192.0.2.10",
        "provisioning_digest": "a" * 64, "credential_revision": 1, **changes})


def ring(active="first"):
    return KEKRing((("first", KEY1), ("second", KEY2)), active_version=active)


def old_binding():
    return AADBinding(tenant_id=OWNER.tenant_id, user_id=OWNER.user_id,
        platform_account_id=BINDING.account_id, connection_id=BINDING.credential_ref,
        broker_uid=BINDING.broker_uid, parent_uid="0", credential_revision=1)


class DemoSecretTests(unittest.TestCase):
    def setUp(self):
        self.spec, self.ring = spec(), ring()
        self.envelope = seal_demo_secret(TRIPLE, self.spec, self.ring)
        self.snapshot = DemoSecretSnapshot(self.spec, self.envelope, storage_version=1)
        self.now, self.reads, self.loads = AT + 100, 0, 0
        self.reader_value = self.snapshot
        self.provider = self.make_provider()

    def read(self, binding, context):
        self.assertEqual(binding, BINDING)
        self.assertEqual(context, OWNER)
        self.reads += 1
        return self.reader_value

    def load(self):
        self.loads += 1
        return self.ring

    def make_provider(self, **changes):
        return SealedDemoReadProvider(self.spec, **{"expected_storage": 1, "read_snapshot": self.read,
            "load_keyring": self.load, "expires_ms": AT + 30_000,
            "milliseconds": lambda: self.now, **changes})

    def test_actual_demo_roundtrip_ciphertext_wire_without_secret(self):
        document = dump_envelope(self.envelope)
        for value in ("synthetic-demo-key", "synthetic-demo-secret", "synthetic-demo-pass"):
            self.assertNotIn(value, document)
        opened = open_demo_secret(load_envelope(document), self.spec, self.ring)
        self.assertEqual(opened._api_key, TRIPLE._api_key)
        self.assertEqual(opened._secret_key, TRIPLE._secret_key)
        self.assertEqual(opened._passphrase, TRIPLE._passphrase)

    def test_demo_and_legacy_real_ciphertexts_are_not_interchangeable(self):
        old = seal(encode_credentials(TRIPLE), old_binding(), self.ring)
        with self.assertRaises(DemoSecretRejected):
            open_demo_secret(old, self.spec, self.ring)
        with self.assertRaises(EnvelopeRejected):
            open_envelope(self.envelope, old_binding(), self.ring)
        with self.assertRaises(EnvelopeRejected):
            seal(encode_credentials(TRIPLE), self.spec, self.ring)
        with self.assertRaises(DemoSecretRejected):
            seal_demo_secret(TRIPLE, old_binding(), self.ring)

    def test_every_binding_parent_ip_purpose_and_provenance_field_authenticates(self):
        changes = [
            spec(binding=replace(BINDING, owner=OTHER)),
            spec(binding=replace(BINDING, account_id=UUID(int=100))),
            spec(binding=replace(BINDING, credential_ref=UUID(int=101))),
            spec(binding=replace(BINDING, broker_uid="999999")),
            spec(parent_uid="123"), spec(egress_ip="192.0.2.11"),
            spec(provisioning_digest="b" * 64), spec(credential_revision=2),
        ]
        for expected in changes:
            with self.subTest(expected=expected), self.assertRaises(DemoSecretRejected):
                open_demo_secret(self.envelope, expected, self.ring)
        original = DemoSecretSpec.record
        for field, changed in (("profile", "real"), ("connection_mode", "real_read_only")):
            def record(item):
                return {**original(item), field: changed}
            with patch.object(DemoSecretSpec, "record", record), self.assertRaises(DemoSecretRejected):
                open_demo_secret(self.envelope, self.spec, self.ring)

    def test_actual_wrap_and_payload_are_independently_authenticated(self):
        for field in ("wrapped_dek", "ciphertext", "payload_nonce", "wrap_nonce"):
            values = {name: getattr(self.envelope, name) for name in
                      ("kek_id", "payload_nonce", "wrap_nonce", "wrapped_dek", "ciphertext")}
            raw = values[field]
            values[field] = bytes((raw[0] ^ 1,)) + raw[1:]
            changed = Envelope(**values)
            with self.subTest(field=field), self.assertRaises(DemoSecretRejected):
                open_demo_secret(changed, self.spec, self.ring)
            with self.assertRaises(DemoSecretRejected):
                rewrap_demo_secret(changed, self.spec, ring("second"))

    def test_actual_kek_rewrap_preserves_payload_and_requires_original_scope(self):
        revised = rewrap_demo_secret(self.envelope, self.spec, ring("second"))
        self.assertEqual(revised.kek_id, "second")
        self.assertEqual(revised.payload_nonce, self.envelope.payload_nonce)
        self.assertEqual(revised.ciphertext, self.envelope.ciphertext)
        self.assertNotEqual(revised.wrap_nonce, self.envelope.wrap_nonce)
        self.assertEqual(open_demo_secret(revised, self.spec, ring("second"))._api_key, TRIPLE._api_key)
        with self.assertRaises(DemoSecretRejected):
            rewrap_demo_secret(self.envelope, spec(credential_revision=2), ring("second"))

    def test_wrong_kek_and_missing_kek_fail_statically(self):
        for keyring in (KEKRing((("first", KEY2),), active_version="first"),
                        KEKRing((("second", KEY2),), active_version="second"), None):
            with self.subTest(keyring=keyring), self.assertRaises(DemoSecretRejected) as raised:
                open_demo_secret(self.envelope, self.spec, keyring)
            self.assertEqual(str(raised.exception), "demo_secret_rejected")

    def test_private_objects_are_immutable_redacted_and_not_picklable(self):
        for obj in (self.spec, self.snapshot, self.provider):
            for private in ("123456", "192.0.2.10", "synthetic-demo"):
                self.assertNotIn(private, repr(obj))
            with self.assertRaises(TypeError):
                pickle.dumps(obj)
            with self.assertRaises(AttributeError):
                obj.untrusted = True

    def test_invalid_demo_purpose_metadata_rejected(self):
        for changes in ({"parent_uid": None}, {"egress_ip": None}, {"provisioning_digest": ""},
                        {"egress_ip": "192.0.2.010"}, {"credential_revision": True},
                        {"credential_revision": 0}, {"credential_revision": 10**15 + 1}):
            with self.subTest(changes=changes), self.assertRaises(DemoSecretRejected):
                spec(**changes)

    def test_provider_rechecks_current_snapshot_and_kek_without_plaintext_cache(self):
        first = self.provider(BINDING, OWNER)
        second = self.provider(BINDING, OWNER)
        self.assertEqual((self.reads, self.loads), (4, 2))
        self.assertEqual(first.record(), second.record())
        self.assertEqual(first.fingerprint(), second.fingerprint())
        self.assertEqual(first.binding, BINDING)
        self.assertEqual(first.expires_ms, AT + 30_000)

    def test_foreign_owner_or_binding_never_loads_snapshot_or_kek(self):
        for binding, owner in ((BINDING, OTHER), (replace(BINDING, account_id=UUID(int=99)), OWNER)):
            with self.subTest(binding=binding), self.assertRaises(DemoSecretRejected):
                self.provider(binding, owner)
        self.assertEqual((self.reads, self.loads), (0, 0))

    def test_expired_or_excessive_lease_never_decrypts(self):
        for now in (AT + 30_000, AT - 40_000):
            self.now = now
            with self.subTest(now=now), self.assertRaises(DemoSecretRejected):
                self.provider(BINDING, OWNER)
        self.assertEqual((self.reads, self.loads), (0, 0))

    def test_missing_paused_revoked_or_stale_snapshot_never_reuses_previous_key(self):
        self.provider(BINDING, OWNER)
        for value in (None, {"status": "revoked"}, "paused",
                      DemoSecretSnapshot(self.spec, self.envelope, storage_version=2),
                      DemoSecretSnapshot(spec(credential_revision=2), self.envelope, storage_version=1)):
            loads = self.loads
            self.reader_value = value
            with self.subTest(value=value), self.assertRaises(DemoSecretRejected):
                self.provider(BINDING, OWNER)
            self.assertEqual(self.loads, loads)

    def test_snapshot_change_while_loading_kek_does_not_return_decrypted_key(self):
        def load():
            self.reader_value = None
            return self.ring
        provider = self.make_provider(load_keyring=load)
        with self.assertRaises(DemoSecretRejected):
            provider(BINDING, OWNER)
        self.assertEqual(self.reads, 2)

    def test_same_revision_ciphertext_fork_after_decrypt_rejects(self):
        replacement = seal_demo_secret(Credentials("other", "other-secret", "other-pass"),
                                       self.spec, self.ring)
        def load():
            self.reader_value = DemoSecretSnapshot(self.spec, replacement, storage_version=1)
            return self.ring
        provider = self.make_provider(load_keyring=load)
        with self.assertRaises(DemoSecretRejected):
            provider(BINDING, OWNER)

    def test_reader_or_keyring_exception_cannot_leak_backend_secret(self):
        def fail(*args):
            raise RuntimeError("synthetic-secret postgres://private")
        for changes in ({"read_snapshot": fail}, {"load_keyring": fail}):
            provider = self.make_provider(**changes)
            with self.subTest(changes=changes), self.assertRaises(DemoSecretRejected) as raised:
                provider(BINDING, OWNER)
            self.assertEqual(str(raised.exception), "demo_secret_rejected")
            self.assertTrue(raised.exception.__suppress_context__)

    def test_provider_deadline_and_backward_clock_rechecked_after_decrypt(self):
        for now in (AT + 30_000, AT + 99):
            self.now = AT + 100
            def load():
                self.now = now
                return self.ring
            provider = self.make_provider(load_keyring=load)
            with self.subTest(now=now), self.assertRaises(DemoSecretRejected):
                provider(BINDING, OWNER)

    def test_invalid_snapshot_and_provider_storage_versions_reject(self):
        for version in (True, 0, 2**63):
            with self.subTest(version=version), self.assertRaises(DemoSecretRejected):
                DemoSecretSnapshot(self.spec, self.envelope, storage_version=version)
            with self.assertRaises(DemoSecretRejected):
                self.make_provider(expected_storage=version)

    def test_sealed_provider_runs_actual_registered_read_client_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry, directory = Path(tmp) / "registry", Path(tmp) / "original"
            for path in (registry, directory): path.mkdir(mode=0o700)
            with RegisteredDemoOutbox.create(registry, directory, binding=BINDING,
                    outbox_id=UUID(int=123), context=OWNER) as box:
                requests = []
                replies = {p.plan.axis: p.response for p in cohort()}
                info = {"userId": BINDING.broker_uid, "parentId": 0, "ips": "192.0.2.10",
                        "authorities": ["coor", "cpor"]}
                def transport(request):
                    requests.append(request)
                    return response(info) if request.axis == "identity" else replies[request.axis]
                client = DemoReadClient(provider=self.provider, transport=transport,
                                        milliseconds=lambda: self.now)
                before = box.receipt
                report = client.capture(box, expectation(), context=OWNER, expected_revision=0)
                self.assertTrue(report.account.matched)
                self.assertFalse(report.native_acceptance_verified)
                self.assertEqual(len(requests), 15)
                self.assertEqual(self.loads, 1 + 15 * 2 + 1)
                self.assertEqual(box.receipt, before)
                self.assertEqual(report.credential_revision, 1)


if __name__ == "__main__":
    unittest.main()
