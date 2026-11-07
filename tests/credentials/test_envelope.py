"""Real AES-GCM with exclusively synthetic keys/payloads; no I/O or accounts."""
import base64
import copy
import dataclasses
import json
import pickle
import unittest
from unittest.mock import patch
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from investalo_credentials import (
    AADBinding, Envelope, EnvelopeRejected, ErrorCode, KEKRing, SecretPayload,
    MAX_DOCUMENT_BYTES, MAX_KEY_SLOTS, MAX_PAYLOAD_BYTES, SCHEMA_VERSION,
    seal, open_envelope, rewrap, dump_envelope, load_envelope,
)
from investalo_credentials import core


KEY_1 = bytes(range(32))
KEY_2 = bytes(range(32, 64))
PAYLOAD = b"synthetic-not-real-api-credential-triple"


def binding(**overrides):
    return AADBinding(**{
        "tenant_id": UUID(int=1), "user_id": UUID(int=2),
        "platform_account_id": UUID(int=3), "connection_id": UUID(int=4),
        "broker_uid": "123456", "parent_uid": "0", "credential_revision": 1,
        **overrides,
    })


def ring(*, active="kek-1"):
    return KEKRing((("kek-1", KEY_1), ("kek-2", KEY_2)), active_version=active)


def envelope_clone(original, **overrides):
    return Envelope(**{
        "schema_version": original.schema_version, "kek_id": original.kek_id,
        "payload_nonce": original.payload_nonce, "wrap_nonce": original.wrap_nonce,
        "wrapped_dek": original.wrapped_dek, "ciphertext": original.ciphertext,
        **overrides,
    })


def changed(value):
    return bytes((value[0] ^ 1,)) + value[1:]


class EnvelopeTests(unittest.TestCase):
    def rejected(self, code, action):
        with self.assertRaises(EnvelopeRejected) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code.value)
        self.assertIsNone(caught.exception.__cause__)
        return caught.exception

    def setUp(self):
        self.binding = binding()
        self.ring = ring()
        self.payload = SecretPayload(PAYLOAD)
        self.envelope = seal(self.payload, self.binding, self.ring)

    def test_published_aes256_gcm_known_vector(self):
        # NIST GCM: 256-bit zero key, 96-bit zero IV, 128-bit zero plaintext,
        # empty additional authenticated data. Final 16 bytes are the tag.
        expected = bytes.fromhex(
            "cea7403d4d606b6e074ec5d3baf39d18"
            "d0d1c8a799996bf0265b98b5d48ab919")
        self.assertEqual(AESGCM(b"\0" * 32).encrypt(b"\0" * 12, b"\0" * 16, b""), expected)
        self.assertEqual(AESGCM(b"\0" * 32).decrypt(b"\0" * 12, expected, b""), b"\0" * 16)

    def test_actual_seal_uses_distinct_canonical_domain_aad_and_exact_sizes(self):
        generated = [b"\x11" * 32, b"\x22" * 12, b"\x33" * 12]
        with patch("investalo_credentials.core.secrets.token_bytes", side_effect=generated) as random:
            actual = seal(self.payload, self.binding, self.ring)
        self.assertEqual([call.args for call in random.call_args_list], [(32,), (12,), (12,)])
        record = {
            "schema_version": SCHEMA_VERSION, "domain": "investalo.credentials.payload",
            "binding": {"tenant_id": str(UUID(int=1)), "user_id": str(UUID(int=2)),
                        "platform_account_id": str(UUID(int=3)), "connection_id": str(UUID(int=4)),
                        "broker_uid": "123456", "parent_uid": "0", "credential_revision": 1,
                        "broker": "bitget", "account_family": "classic_v2",
                        "connection_mode": "real_read_only"},
        }
        aad = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("ascii")
        self.assertEqual(actual.ciphertext, AESGCM(generated[0]).encrypt(generated[1], PAYLOAD, aad))
        wrap = {**record, "domain": "investalo.credentials.dek-wrap", "kek_id": "kek-1"}
        wrap_aad = json.dumps(wrap, sort_keys=True, separators=(",", ":")).encode("ascii")
        self.assertEqual(AESGCM(KEY_1).decrypt(actual.wrap_nonce, actual.wrapped_dek, wrap_aad),
                         generated[0])
        self.assertNotEqual(aad, wrap_aad)

    def test_roundtrip_explicit_ciphertext_only_serialization(self):
        dumped = dump_envelope(self.envelope)
        self.assertLess(len(dumped.encode()), MAX_DOCUMENT_BYTES)
        self.assertNotIn(PAYLOAD.decode(), dumped)
        self.assertEqual(set(json.loads(dumped)), {
            "schema_version", "kek_id", "payload_nonce", "wrap_nonce", "wrapped_dek", "ciphertext"})
        for loaded in (load_envelope(dumped), load_envelope(dumped.encode())):
            self.assertEqual(open_envelope(loaded, self.binding, self.ring).reveal(), PAYLOAD)
            self.assertEqual(dump_envelope(loaded), dumped)

    def test_every_mutable_binding_field_is_authenticated(self):
        replacements = {
            "tenant_id": UUID(int=10), "user_id": UUID(int=11),
            "platform_account_id": UUID(int=12), "connection_id": UUID(int=13),
            "broker_uid": "999", "parent_uid": None, "credential_revision": 2,
        }
        for field, value in replacements.items():
            expected = binding(**{field: value})
            self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                          lambda: open_envelope(self.envelope, expected, self.ring))
        # The literal fields are constructor-restricted AND covered by the tag.
        # Deliberate corruption models a faulty future host; no serialization is
        # used to produce or trust an expected binding.
        for field, value in (("broker", "other"), ("account_family", "uta"),
                             ("connection_mode", "live")):
            expected = binding()
            object.__setattr__(expected, field, value)
            self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                          lambda: open_envelope(self.envelope, expected, self.ring))
            self.rejected(ErrorCode.INVALID_BINDING, lambda: binding(**{field: value}))

    def test_nullable_parent_zero_and_positive_uid_remain_distinct(self):
        unknown = binding(parent_uid=None)
        unknown_envelope = seal(self.payload, unknown, self.ring)
        self.assertEqual(open_envelope(unknown_envelope, unknown, self.ring).reveal(), PAYLOAD)
        for other in (binding(parent_uid="0"), binding(parent_uid="777")):
            self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                          lambda: open_envelope(unknown_envelope, other, self.ring))

    def test_every_ciphertext_field_and_kek_id_is_authenticated(self):
        for name in ("payload_nonce", "wrap_nonce", "wrapped_dek", "ciphertext"):
            altered = envelope_clone(self.envelope, **{name: changed(getattr(self.envelope, name))})
            self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                          lambda: open_envelope(altered, self.binding, self.ring))
        swapped_id = envelope_clone(self.envelope, kek_id="kek-2")
        self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                      lambda: open_envelope(swapped_id, self.binding, self.ring))
        for schema in ("credential-envelope/2", "", None, 1):
            self.rejected(ErrorCode.INVALID_ENVELOPE,
                          lambda: envelope_clone(self.envelope, schema_version=schema))

    def test_component_swap_between_same_binding_envelopes_rejected(self):
        other = seal(SecretPayload(b"different-synthetic-payload"), self.binding, self.ring)
        altered = envelope_clone(self.envelope, wrapped_dek=other.wrapped_dek, wrap_nonce=other.wrap_nonce)
        self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                      lambda: open_envelope(altered, self.binding, self.ring))
        altered = envelope_clone(self.envelope, ciphertext=other.ciphertext, payload_nonce=other.payload_nonce)
        self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                      lambda: open_envelope(altered, self.binding, self.ring))

    def test_wrong_key_material_and_missing_old_version(self):
        wrong = KEKRing((("kek-1", KEY_2),), active_version="kek-1")
        self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                      lambda: open_envelope(self.envelope, self.binding, wrong))
        missing = KEKRing((("kek-2", KEY_2),), active_version="kek-2")
        self.rejected(ErrorCode.KEY_UNAVAILABLE,
                      lambda: open_envelope(self.envelope, self.binding, missing))

    def test_random_seals_are_distinct_for_same_payload_and_binding(self):
        envelopes = [seal(self.payload, self.binding, self.ring) for _ in range(8)]
        self.assertEqual(len({item.payload_nonce for item in envelopes}), 8)
        self.assertEqual(len({item.wrap_nonce for item in envelopes}), 8)
        self.assertEqual(len({item.ciphertext for item in envelopes}), 8)
        self.assertEqual(len({item.wrapped_dek for item in envelopes}), 8)
        for item in envelopes:
            self.assertEqual(open_envelope(item, self.binding, self.ring).reveal(), PAYLOAD)

    def test_rotation_authenticates_full_payload_and_preserves_ciphertext(self):
        before = dump_envelope(self.envelope)
        rotated = rewrap(self.envelope, self.binding, ring(active="kek-2"))
        self.assertEqual(rotated.kek_id, "kek-2")
        self.assertNotEqual(rotated.wrap_nonce, self.envelope.wrap_nonce)
        self.assertNotEqual(rotated.wrapped_dek, self.envelope.wrapped_dek)
        self.assertEqual(rotated.payload_nonce, self.envelope.payload_nonce)
        self.assertEqual(rotated.ciphertext, self.envelope.ciphertext)
        self.assertEqual(dump_envelope(self.envelope), before)
        new_only = KEKRing((("kek-2", KEY_2),), active_version="kek-2")
        self.assertEqual(open_envelope(rotated, self.binding, new_only).reveal(), PAYLOAD)
        restored_old = KEKRing((("kek-1", KEY_1),), active_version="kek-1")
        self.assertEqual(open_envelope(load_envelope(before), self.binding, restored_old).reveal(), PAYLOAD)
        self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                      lambda: open_envelope(rotated, binding(credential_revision=2), new_only))

    def test_same_active_version_rewrap_still_uses_new_nonce(self):
        again = rewrap(self.envelope, self.binding, self.ring)
        self.assertEqual(again.kek_id, "kek-1")
        self.assertNotEqual(again.wrap_nonce, self.envelope.wrap_nonce)
        self.assertEqual(again.ciphertext, self.envelope.ciphertext)
        self.assertEqual(open_envelope(again, self.binding, self.ring).reveal(), PAYLOAD)

    def test_rewrap_rejects_tampered_payload_before_randomness_or_new_wrap(self):
        altered = envelope_clone(self.envelope, ciphertext=changed(self.envelope.ciphertext))
        with patch("investalo_credentials.core.secrets.token_bytes") as random:
            self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                          lambda: rewrap(altered, self.binding, ring(active="kek-2")))
            random.assert_not_called()
        with patch("investalo_credentials.core.secrets.token_bytes") as random:
            self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                          lambda: rewrap(self.envelope, binding(user_id=UUID(int=8)), self.ring))
            random.assert_not_called()

    def test_keyring_limits_uniqueness_and_immutable_versions(self):
        cases = ((), [("kek-1", KEY_1)], (("kek-1", KEY_1), ("kek-1", KEY_2)),
                 (("bad version", KEY_1),), (("kek-1", b"x" * 31),),
                 (("kek-1", bytearray(KEY_1)),),
                 tuple((f"k-{i}", KEY_1) for i in range(MAX_KEY_SLOTS + 1)),
                 ((("not", "id"), KEY_1),))
        for entries in cases:
            self.rejected(ErrorCode.INVALID_KEYRING,
                          lambda: KEKRing(entries, active_version="kek-1"))
        self.rejected(ErrorCode.INVALID_KEYRING,
                      lambda: KEKRing((("kek-1", KEY_1),), active_version="missing"))
        self.rejected(ErrorCode.INVALID_KEYRING,
                      lambda: KEKRing((("kek-1", KEY_1), ("alias", KEY_1)), active_version="alias"))
        with self.assertRaises(AttributeError):
            self.ring.active_version = "kek-2"

    def test_binding_limits_ascii_uid_and_positive_integer_revision(self):
        for field in ("tenant_id", "user_id", "platform_account_id", "connection_id"):
            self.rejected(ErrorCode.INVALID_BINDING, lambda: binding(**{field: str(UUID(int=1))}))
        for value in ("", "0", "12٢", 123, "1" * 21):
            self.rejected(ErrorCode.INVALID_BINDING, lambda: binding(broker_uid=value))
        for value in ("", 0, "12٢"):
            self.rejected(ErrorCode.INVALID_BINDING, lambda: binding(parent_uid=value))
        for value in (0, -1, True, "1", 2**63):
            self.rejected(ErrorCode.INVALID_BINDING, lambda: binding(credential_revision=value))

    def test_payload_limits_and_opaque_bytes_only(self):
        for value in (b"", PAYLOAD.decode(), bytearray(PAYLOAD), b"x" * (MAX_PAYLOAD_BYTES + 1)):
            self.rejected(ErrorCode.INVALID_PAYLOAD, lambda: SecretPayload(value))
        largest = SecretPayload(b"x" * MAX_PAYLOAD_BYTES)
        encrypted = seal(largest, self.binding, self.ring)
        self.assertLess(len(dump_envelope(encrypted)), MAX_DOCUMENT_BYTES)
        self.assertEqual(open_envelope(encrypted, self.binding, self.ring).reveal(), largest.reveal())

    def test_load_rejects_duplicate_unknown_missing_and_malformed_documents(self):
        raw = json.loads(dump_envelope(self.envelope))
        documents = (
            json.dumps({**raw, "unexpected": "value"}),
            json.dumps({key: value for key, value in raw.items() if key != "kek_id"}),
            '{"kek_id":"first","kek_id":"second"}',
            json.dumps({**raw, "kek_id": 3}), json.dumps({**raw, "schema_version": "other/1"}),
            '[]', 'null', '{"ciphertext":NaN}', b"\xff", "\ud800", "", 1,
            b"x" * (MAX_DOCUMENT_BYTES + 1), "x" * (MAX_DOCUMENT_BYTES + 1),
        )
        for document in documents:
            self.rejected(ErrorCode.INVALID_ENVELOPE, lambda: load_envelope(document))

    def test_base64_must_be_ascii_canonical_and_lengths_exact(self):
        raw = json.loads(dump_envelope(self.envelope))
        invalid = {
            "payload_nonce": ["", "A" * 16 + "\n", "!" * 16, "Ａ" * 16,
                              base64.b64encode(b"x" * 11).decode(),
                              base64.b64encode(b"x" * 13).decode(), "A" * 10000],
            "wrap_nonce": [None, 1, False, [], ""],
            "wrapped_dek": [base64.b64encode(b"x" * 47).decode()],
            "ciphertext": [base64.b64encode(b"x" * 16).decode(),
                           base64.b64encode(b"x" * (MAX_PAYLOAD_BYTES + 17)).decode()],
        }
        for field, values in invalid.items():
            for value in values:
                self.rejected(ErrorCode.INVALID_ENVELOPE,
                              lambda: load_envelope(json.dumps({**raw, field: value})))
        # Nonzero Base64 padding bits decode to the same bytes; reject aliases.
        self.assertEqual(base64.b64decode("Zh==", validate=True), b"f")
        self.rejected(ErrorCode.INVALID_ENVELOPE, lambda: core._unbase64("Zh==", 1))
        self.rejected(ErrorCode.INVALID_ENVELOPE,
                      lambda: load_envelope(json.dumps({**raw, "ciphertext": raw["ciphertext"] + "="})))

    def test_objects_never_incidentally_serialize_or_print_secrets(self):
        values = (self.payload, self.ring, self.binding, self.envelope)
        for value in values:
            printed = repr(value) + str(value)
            for secret in (PAYLOAD.decode(), KEY_1.hex(), repr(KEY_1), "123456"):
                self.assertNotIn(secret, printed)
            for operation in (pickle.dumps, dataclasses.asdict, copy.copy, copy.deepcopy):
                with self.assertRaises(TypeError):
                    operation(value)
            self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(AttributeError):
            self.payload._bytes = b"changed"
        with self.assertRaises(AttributeError):
            self.envelope.ciphertext = b"changed"
        with self.assertRaises(TypeError):
            json.dumps(self.payload)

    def test_backend_randomness_errors_are_static_and_chain_suppressed(self):
        with patch("investalo_credentials.core.secrets.token_bytes",
                   side_effect=RuntimeError("synthetic-secret-backend")):
            error = self.rejected(ErrorCode.CRYPTO_FAILURE,
                                  lambda: seal(self.payload, self.binding, self.ring))
        self.assertTrue(error.__suppress_context__)
        self.assertNotIn("synthetic-secret", repr(error))
        with patch("investalo_credentials.core.AESGCM",
                   side_effect=RuntimeError("synthetic-secret-backend")):
            error = self.rejected(ErrorCode.AUTHENTICATION_FAILED,
                                  lambda: open_envelope(self.envelope, self.binding, self.ring))
        self.assertTrue(error.__suppress_context__)

    def test_invalid_public_argument_types_rejected_before_crypto(self):
        for action, code in (
            (lambda: seal(PAYLOAD, self.binding, self.ring), ErrorCode.INVALID_PAYLOAD),
            (lambda: seal(self.payload, None, self.ring), ErrorCode.INVALID_BINDING),
            (lambda: seal(self.payload, self.binding, None), ErrorCode.INVALID_KEYRING),
            (lambda: open_envelope(None, self.binding, self.ring), ErrorCode.INVALID_ENVELOPE),
            (lambda: rewrap({}, self.binding, self.ring), ErrorCode.INVALID_ENVELOPE),
            (lambda: dump_envelope(self.payload), ErrorCode.INVALID_ENVELOPE),
        ):
            self.rejected(code, action)


if __name__ == "__main__":
    unittest.main()
