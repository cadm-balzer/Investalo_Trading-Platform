"""Dedicated assertion fixtures; no broker, file provider, HTTP or real identity."""
import base64
import dataclasses
import hashlib
import hmac
import json
import pickle
import unittest
from uuid import UUID

from investalo_credential_store.request_assertion import (
    MAX_BODY_BYTES, OnboardingRejected, RequestVerifier, TARGETS,
)


SIGNING_KEY = b"synthetic-action-signing-key-32-bytes"
ISSUER = "https://identity.fixture.invalid"
NOW = 1700000000
TENANT = str(UUID(int=11))
NONCE = str(UUID(int=12))
BODY = b'{"fixture":true}'


def make_claims(*, body=BODY, action="register", now=NOW, tenant_id=TENANT,
                subject="opaque-fixture-sub", oidc_issuer=ISSUER, **overrides):
    """Root's synthetic E2E may override time, stored actor, epoch and fresh JTI."""
    return {
        "iss": "investalo-bff", "aud": "investalo-credentials", "sub": subject,
        "oidc_iss": oidc_issuer, "oidc_auth_time": now - 1,
        "oidc_amr": ["pwd", "mfa"], "step_up_started_at": now - 2,
        "tenant_id": tenant_id, "auth_epoch": 0, "jti": NONCE,
        "iat": now, "exp": now + 60, "htm": "POST",
        "htu": TARGETS[action], "body_sha256": hashlib.sha256(body).hexdigest(),
        **overrides,
    }


def _base64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def sign_assertion(claims, *, key=SIGNING_KEY, header=None,
                   payload_json=None, header_json=None):
    """Test-only HS256 signer, with raw JSON hooks for parser negative cases."""
    if header_json is None:
        header_json = json.dumps(header or {"alg": "HS256", "typ": "JWT"},
                                 sort_keys=True, separators=(",", ":"))
    if payload_json is None:
        payload_json = json.dumps(claims, sort_keys=True, separators=(",", ":"))
    encoded = _base64(header_json.encode()) + "." + _base64(payload_json.encode())
    signature = hmac.digest(key, encoded.encode("ascii"), "sha256")
    return encoded + "." + _base64(signature)


class AssertionTests(unittest.TestCase):
    def setUp(self):
        self.verifier = RequestVerifier(key=SIGNING_KEY, oidc_issuer=ISSUER,
                                        clock=lambda: NOW)

    def rejected(self, token, *, action="register", body=BODY,
                 verifier=None, code="authentication_required"):
        with self.assertRaises(OnboardingRejected) as caught:
            (verifier or self.verifier).verify(token, action=action, body=body)
        error = caught.exception
        self.assertEqual(error.code, code)
        self.assertEqual(str(error), code)
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)
        for sensitive in ("opaque-fixture-sub", ISSUER, BODY.decode(),
                          SIGNING_KEY.decode(), "synthetic-private-secret"):
            self.assertNotIn(sensitive, repr(error) + str(error))
        return error

    def test_dedicated_assertion_preserves_opaque_actor_and_canonical_identifiers(self):
        claims = make_claims(subject="opaque:subject/with-punctuation")
        actual = self.verifier.verify(sign_assertion(claims), action="register", body=BODY)
        self.assertEqual(actual.subject, claims["sub"])
        self.assertEqual(actual.issuer, ISSUER)
        self.assertEqual(actual.tenant_id, UUID(TENANT))
        self.assertEqual(actual.nonce, UUID(NONCE))
        self.assertEqual(actual.auth_epoch, 0)
        self.assertEqual(actual.auth_time, NOW - 1)
        self.assertEqual(actual.started_at, NOW - 2)
        self.assertEqual(actual.expires_at, NOW + 60)

    def test_every_supported_action_is_bound_to_its_exact_route_and_body(self):
        for action in TARGETS:
            raw = json.dumps({"action": action}).encode()
            token = sign_assertion(make_claims(action=action, body=raw))
            self.verifier.verify(token, action=action, body=raw)
            for other in TARGETS:
                if other != action:
                    self.rejected(token, action=other, body=raw)
            self.rejected(token, action=action, body=raw + b" ")
        self.rejected(sign_assertion(make_claims()), action="withdraw")

    def test_wrong_key_unsigned_algorithm_and_header_extensions_rejected(self):
        self.rejected(sign_assertion(make_claims(), key=b"different-fixture-key" * 2))
        for header in (
            {"alg": "none", "typ": "JWT"}, {"alg": "RS256", "typ": "JWT"},
            {"alg": "HS384", "typ": "JWT"}, {"alg": "HS256", "typ": "JWT", "kid": "untrusted"},
            {"alg": "HS256", "typ": "other"}, {"alg": "HS256"},
        ):
            self.rejected(sign_assertion(make_claims(), header=header))
        for token in ("", "a.b", "a.b.c.d", "a.b.", "not-a-token"):
            self.rejected(token)

    def test_payload_change_with_old_signature_is_rejected(self):
        original = sign_assertion(make_claims())
        header, _, signature = original.split(".")
        changed = json.dumps(make_claims(sub="synthetic-private-secret")).encode()
        self.rejected(".".join((header, _base64(changed), signature)))

    def test_signature_base64_padding_and_noncanonical_padding_bits_rejected(self):
        token = sign_assertion(make_claims())
        header, payload, signature = token.split(".")
        self.rejected(".".join((header, payload, signature + "=")))
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        last = alphabet.index(signature[-1])
        alias = signature[:-1] + alphabet[last | 1]
        self.assertNotEqual(alias, signature)
        self.assertEqual(base64.urlsafe_b64decode(signature + "="),
                         base64.urlsafe_b64decode(alias + "="))
        self.rejected(".".join((header, payload, alias)))
        self.rejected(".".join((header + "=", payload, signature)))
        self.rejected(".".join((header, payload + "=", signature)))

    def test_token_type_length_and_body_type_limits_fail_closed(self):
        valid = sign_assertion(make_claims())
        for token in (None, 1, b"token", "x" * 8193):
            self.rejected(token)
        for body in (None, BODY.decode(), bytearray(BODY), b"", b"x" * (MAX_BODY_BYTES + 1)):
            self.rejected(valid, body=body)
        for action in (None, 1, True, "REGISTER", "../register"):
            self.rejected(valid, action=action)

    def test_exact_issuer_audience_request_method_route_and_digest(self):
        replacements = {
            "iss": "other-bff", "aud": "investalo-api", "oidc_iss": ISSUER + "/",
            "htm": "GET", "htu": TARGETS["register"] + "?anything=1",
            "body_sha256": hashlib.sha256(b"other").hexdigest(),
        }
        for field, value in replacements.items():
            self.rejected(sign_assertion(make_claims(**{field: value})))
        for audience in (["investalo-credentials"], None, "investalo-credentials "):
            self.rejected(sign_assertion(make_claims(aud=audience)))

    def test_request_uuid_claims_require_canonical_strings(self):
        for field in ("tenant_id", "jti"):
            valid = make_claims()[field]
            for value in (None, 1, "", valid.replace("-", ""), "{" + valid + "}",
                          "urn:uuid:" + valid, "not-a-uuid"):
                self.rejected(sign_assertion(make_claims(**{field: value})))
        uppercase = "ABCDEFAB-1234-5678-90AB-ABCDEFABCDEF"
        for field in ("tenant_id", "jti"):
            self.rejected(sign_assertion(make_claims(**{field: uppercase})))

    def test_unknown_missing_and_duplicate_claims_rejected_even_when_signed(self):
        claims = make_claims()
        self.rejected(sign_assertion({**claims, "role": "owner"}))
        for missing in claims:
            self.rejected(sign_assertion({key: value for key, value in claims.items() if key != missing}))
        raw = json.dumps(claims, separators=(",", ":"))
        duplicate = raw[:-1] + ',"aud":"investalo-credentials"}'
        self.rejected(sign_assertion(claims, payload_json=duplicate))
        self.rejected(sign_assertion(claims, header_json='{"alg":"HS256","alg":"HS256","typ":"JWT"}'))
        for raw in ("null", "[]", "1", '{"auth_epoch":NaN}'):
            self.rejected(sign_assertion(claims, payload_json=raw))

    def test_integer_claims_reject_bool_float_negative_and_overflow(self):
        for field in ("iat", "exp", "oidc_auth_time", "step_up_started_at", "auth_epoch"):
            for value in (True, False, 1.0, "1", None, -1, 2**63):
                self.rejected(sign_assertion(make_claims(**{field: value})))
        maximum = make_claims(auth_epoch=2**63 - 1)
        actual = self.verifier.verify(sign_assertion(maximum), action="register", body=BODY)
        self.assertEqual(actual.auth_epoch, 2**63 - 1)

    def test_mfa_authentication_must_not_predate_stepup_even_if_recent(self):
        self.rejected(sign_assertion(make_claims(
            oidc_auth_time=NOW - 10, step_up_started_at=NOW - 9)))
        accepted = make_claims(oidc_auth_time=NOW - 10, step_up_started_at=NOW - 10)
        self.verifier.verify(sign_assertion(accepted), action="register", body=BODY)

    def test_fresh_authentication_and_stepup_have_separate_bounded_windows(self):
        self.verifier.verify(sign_assertion(make_claims(
            oidc_auth_time=NOW - 120, step_up_started_at=NOW - 300)),
            action="register", body=BODY)
        self.rejected(sign_assertion(make_claims(
            oidc_auth_time=NOW - 121, step_up_started_at=NOW - 121)))
        self.rejected(sign_assertion(make_claims(
            oidc_auth_time=NOW - 1, step_up_started_at=NOW - 301)))
        self.rejected(sign_assertion(make_claims(
            oidc_auth_time=NOW + 6, step_up_started_at=NOW)))
        self.rejected(sign_assertion(make_claims(
            oidc_auth_time=NOW + 1, step_up_started_at=NOW, iat=NOW - 5)))

    def test_future_tolerance_does_not_allow_an_earlier_authentication(self):
        accepted = make_claims(iat=NOW + 5, exp=NOW + 60,
                               oidc_auth_time=NOW + 5, step_up_started_at=NOW)
        self.verifier.verify(sign_assertion(accepted), action="register", body=BODY)
        self.rejected(sign_assertion(make_claims(iat=NOW + 6, exp=NOW + 60)))
        self.rejected(sign_assertion(make_claims(
            oidc_auth_time=NOW - 1, step_up_started_at=NOW)))

    def test_short_assertion_expiry_and_issue_age_boundaries(self):
        self.rejected(sign_assertion(make_claims(exp=NOW)))
        self.rejected(sign_assertion(make_claims(exp=NOW + 61)))
        self.rejected(sign_assertion(make_claims(iat=NOW + 5, exp=NOW + 61)))
        self.rejected(sign_assertion(make_claims(iat=NOW - 61, exp=NOW + 1)))
        accepted = make_claims(iat=NOW - 59, exp=NOW + 1,
                               oidc_auth_time=NOW - 60, step_up_started_at=NOW - 61)
        self.verifier.verify(sign_assertion(accepted), action="register", body=BODY)
        expired_verifier = RequestVerifier(key=SIGNING_KEY, oidc_issuer=ISSUER,
                                          clock=lambda: NOW + 60)
        self.rejected(sign_assertion(make_claims()), verifier=expired_verifier)

    def test_amr_requires_unique_bounded_string_methods_and_mfa(self):
        for amr in (
            [], ["pwd"], "mfa", None, ["mfa", "mfa"], ["mfa", True],
            ["mfa", ""], ["mfa", "X"], ["mfa", "x" * 33],
            ["mfa"] + [f"m{i}" for i in range(8)],
        ):
            self.rejected(sign_assertion(make_claims(oidc_amr=amr)))
        self.verifier.verify(sign_assertion(make_claims(oidc_amr=["mfa"])),
                             action="register", body=BODY)

    def test_opaque_subject_limits_and_controls(self):
        for subject in ("", None, 7, "x" * 256, "x\n", "x\x00", "x\x7f"):
            self.rejected(sign_assertion(make_claims(sub=subject)))
        self.verifier.verify(sign_assertion(make_claims(subject="x" * 255)),
                             action="register", body=BODY)

    def test_constructor_rejects_weak_nonbytes_keys_and_untrusted_issuer_forms(self):
        for key in (None, SIGNING_KEY.decode(), bytearray(SIGNING_KEY), b"x" * 31, b"x" * 129):
            with self.assertRaises(OnboardingRejected) as caught:
                RequestVerifier(key=key, oidc_issuer=ISSUER)
            self.assertEqual(str(caught.exception), "invalid_context")
            self.assertIsNone(caught.exception.__cause__)
        for issuer in (None, [], "", "http://identity.fixture.invalid",
                       "https://user:password@identity.fixture.invalid",
                       ISSUER + "?query=value", ISSUER + "#fragment", "https://"):
            with self.assertRaises(OnboardingRejected) as caught:
                RequestVerifier(key=SIGNING_KEY, oidc_issuer=issuer)
            self.assertEqual(str(caught.exception), "invalid_context")
        with self.assertRaises(OnboardingRejected):
            RequestVerifier(key=SIGNING_KEY, oidc_issuer=ISSUER, clock=NOW)
        for size in (32, 128):
            RequestVerifier(key=b"x" * size, oidc_issuer=ISSUER)

    def test_private_assertion_and_verifier_have_redacted_nonserializing_representations(self):
        assertion = self.verifier.verify(sign_assertion(make_claims()), action="register", body=BODY)
        for value in (self.verifier, assertion):
            for secret in (SIGNING_KEY.decode(), "opaque-fixture-sub", ISSUER, TENANT, NONCE):
                self.assertNotIn(secret, repr(value) + str(value))
            for serialize in (pickle.dumps, dataclasses.asdict):
                with self.assertRaises(TypeError):
                    serialize(value)
            self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises(AttributeError):
            assertion.auth_epoch = 100

    def test_clock_backend_error_does_not_escape_with_sensitive_context(self):
        def failed_clock():
            raise RuntimeError("synthetic-private-secret")
        verifier = RequestVerifier(key=SIGNING_KEY, oidc_issuer=ISSUER, clock=failed_clock)
        self.rejected(sign_assertion(make_claims()), verifier=verifier)


if __name__ == "__main__":
    unittest.main()
