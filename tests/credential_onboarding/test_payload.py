"""Private codec fixtures only; no actual API key, account or network."""
import dataclasses
import json
import pickle
import unittest

from investalo_bitget import Credentials, SignedReadRequest
from investalo_credentials import SecretPayload
from investalo_credential_store.bitget_payload import (
    SCHEMA_VERSION, PayloadRejected, encode_credentials, decode_credentials,
)


def raw(**overrides):
    return json.dumps({"schema_version": SCHEMA_VERSION, "api_key": "fixture-key",
                       "secret": "fixture-secret", "passphrase": "fixture-pass", **overrides},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class PayloadTests(unittest.TestCase):
    def rejected(self, action):
        with self.assertRaises(PayloadRejected) as caught:
            action()
        self.assertEqual(str(caught.exception), "invalid_bitget_payload")
        self.assertIsNone(caught.exception.__cause__)
        for value in ("fixture-key", "fixture-secret", "fixture-pass"):
            self.assertNotIn(value, repr(caught.exception))
        return caught.exception

    def test_canonical_roundtrip_preserves_exact_signing_bytes(self):
        original = Credentials("fixture-key", "fixture-secret", "fixture-pass")
        payload = encode_credentials(original)
        self.assertEqual(payload.reveal(), raw())
        decoded = decode_credentials(payload)
        request = lambda creds: SignedReadRequest(creds, "/api/v2/spot/account/info", (), 1700000000123)
        self.assertEqual(dict(request(original).headers), dict(request(decoded).headers))

    def test_legitimate_utf8_secret_preserved_without_normalization(self):
        original = Credentials("fixture-key", "öffentlicher-fixture-secret", "fixture-pass")
        decoded = decode_credentials(encode_credentials(original))
        self.assertEqual(decoded._secret_key, original._secret_key)
        self.assertNotEqual(decoded._secret_key, b"offentlicher-fixture-secret")

    def test_exact_maximum_lengths_and_internal_spaces(self):
        original = Credentials("k" * 256, "s" * 1024, "p" * 256)
        payload = encode_credentials(original)
        self.assertLessEqual(len(payload.reveal()), 4096)
        self.assertEqual(decode_credentials(payload)._secret_key, b"s" * 1024)
        original = Credentials("fixture key", "fixture secret ", "fixture pass")
        self.assertEqual(decode_credentials(encode_credentials(original))._secret_key, b"fixture secret ")

    def test_no_incidental_plaintext_repr_or_automatic_serialization(self):
        payload = encode_credentials(Credentials("fixture-key", "fixture-secret", "fixture-pass"))
        decoded = decode_credentials(payload)
        for value in (payload, decoded):
            for secret in ("fixture-key", "fixture-secret", "fixture-pass"):
                self.assertNotIn(secret, repr(value) + str(value))
            for operation in (pickle.dumps, dataclasses.asdict):
                with self.assertRaises(TypeError):
                    operation(value)

    def test_duplicate_extra_missing_or_wrong_schema_rejected(self):
        records = (
            raw(schema_version="bitget-credentials/2"),
            raw(schema_version=True),
            raw(unexpected="extra"),
            b'{"api_key":"fixture-key","api_key":"other"}',
            b'{"schema_version":"bitget-credentials/1","secret":"fixture-secret","passphrase":"fixture-pass"}',
            b"[]", b"null", b'{"secret":NaN}', b"\xff",
        )
        for value in records:
            self.rejected(lambda: decode_credentials(SecretPayload(value)))

    def test_noncanonical_json_utf8_bom_spaces_key_order_escapes_rejected(self):
        records = (
            b" " + raw(), raw() + b"\n", b"\xef\xbb\xbf" + raw(),
            json.dumps(json.loads(raw()), indent=2).encode(),
            b'{"secret":"fixture-secret","api_key":"fixture-key","passphrase":"fixture-pass",'
            b'"schema_version":"bitget-credentials/1"}',
            raw().replace(b"fixture-key", b"fixture-\\u006bey"),
        )
        for value in records:
            self.rejected(lambda: decode_credentials(SecretPayload(value)))

    def test_existing_credentials_limits_reused_for_all_three_fields(self):
        for field, value in (
            ("api_key", ""), ("api_key", "x" * 257), ("api_key", " key"),
            ("api_key", "key "), ("api_key", "clé"),
            ("secret", ""), ("secret", "x" * 1025), ("secret", "é" * 513),
            ("passphrase", ""), ("passphrase", "x" * 257), ("passphrase", " pass"),
        ):
            self.rejected(lambda: decode_credentials(SecretPayload(raw(**{field: value}))))

    def test_controls_surrogates_format_characters_and_nonstring_values_rejected(self):
        for field in ("api_key", "secret", "passphrase"):
            for value in (True, False, 1, None, [], {}, "key\x00", "key\x7f",
                          "key\x85", "key\u202e", "key\u200d"):
                self.rejected(lambda: decode_credentials(SecretPayload(raw(**{field: value}))))
        escaped = raw().replace(b"fixture-secret", b"fixture-\\ud800secret")
        self.rejected(lambda: decode_credentials(SecretPayload(escaped)))
        # The older adapter permits some C1/format secret characters; the new
        # persistence codec deliberately rejects these without changing it.
        for secret in ("fixture\x85secret", "fixture\u202esecret"):
            credentials = Credentials("fixture-key", secret, "fixture-pass")
            self.rejected(lambda: encode_credentials(credentials))

    def test_invalid_argument_types_and_corrupt_private_adapter_slots_safe(self):
        for value in (None, {}, raw(), "raw"):
            self.rejected(lambda: encode_credentials(value))
            self.rejected(lambda: decode_credentials(value))
        credentials = Credentials("fixture-key", "fixture-secret", "fixture-pass")
        object.__setattr__(credentials, "_secret_key", b"\xffprivate")
        error = self.rejected(lambda: encode_credentials(credentials))
        self.assertTrue(error.__suppress_context__)


if __name__ == "__main__":
    unittest.main()
