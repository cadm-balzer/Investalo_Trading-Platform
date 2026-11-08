"""Offline synthetic passkey handoff fixtures; no receipt consumer or broker."""
import base64
import dataclasses
import hashlib
import hmac
import json
import pickle
import unittest
from types import MappingProxyType
from uuid import UUID

from investalo_credential_store.passkey_request_assertion import (
    AUDIENCE, AUTHORIZATION_KIND, MAX_BODY_BYTES, MAX_SAFE_INTEGER, TARGETS,
    PasskeyActionAssertion, PasskeyRequestContext, PasskeyRequestVerifier,
)
from investalo_credential_store.request_assertion import (
    ActionAssertion, OnboardingRejected, RequestVerifier,
)
from test_assertions import make_claims as old_claims, sign_assertion as old_sign


KEY = b"synthetic-passkey-dedicated-key-32"
ISSUER = "https://identity.fixture.invalid"
ORIGIN = "https://cockpit.fixture.invalid:8443"
NOW = 1700000000
TENANT = UUID(int=1001)
USER = UUID(int=1002)
ACCOUNT = str(UUID(int=1003))
CONNECTION = str(UUID(int=1004))
SUBJECT = "opaque:fixture/subject"
SESSION_BINDING = "ab" * 32
METADATA_SHA256 = "cd" * 32
TRIPLE = {"api_key": "synthetic-key", "secret": "synthetic-private-secret",
          "passphrase": "synthetic-passphrase"}


def fixture_target(action="register", **overrides):
    result = {"action": action, "platform_account_id": ACCOUNT, "connection_id": CONNECTION}
    if action != "register":
        result.update(expected_revision=3, expected_storage=5)
    return {**result, **overrides}


def fixture_body(action="register", *, target=None, triple=None):
    body = dict(target or fixture_target(action))
    body.pop("action")
    if action != "revoke":
        body["credentials"] = TRIPLE if triple is None else triple
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def fixture_context(**overrides):
    return PasskeyRequestContext(**{
        "tenant_id": TENANT, "user_id": USER, "subject": SUBJECT, "auth_epoch": 2,
        "oidc_auth_time": NOW - 86400, "session_binding": SESSION_BINDING,
        "session_expires_at": NOW + 600, **overrides,
    })


def fixture_claims(action="register", *, body=None, target=None, **overrides):
    body = fixture_body(action) if body is None else body
    return {
        "iss": "investalo-bff", "aud": AUDIENCE, "sub": SUBJECT,
        "authorization_kind": AUTHORIZATION_KIND,
        "authorization_id": str(UUID(int=1010)), "proof_id": str(UUID(int=1011)),
        "grant_id": str(UUID(int=1012)), "tenant_id": str(TENANT), "user_id": str(USER),
        "auth_epoch": 2, "oidc_iss": ISSUER, "oidc_auth_time": NOW - 86400,
        "rp_id": "cockpit.fixture.invalid", "origin": ORIGIN,
        "session_binding": SESSION_BINDING, "session_expires_at": NOW + 600,
        "passkey_id": str(UUID(int=1013)), "passkey_version": 2,
        "passkey_started_at": NOW - 15, "passkey_checked_at": NOW - 10,
        "passkey_authorized_at": NOW - 5, "authorization_expires_at": NOW + 100,
        "metadata_sha256": METADATA_SHA256,
        "target": fixture_target(action) if target is None else target,
        "iat": NOW, "exp": NOW + 60, "jti": str(UUID(int=1014)),
        "htm": "POST", "htu": TARGETS[action],
        "body_sha256": hashlib.sha256(body).hexdigest(), **overrides,
    }


def _base64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def sign_assertion(claims, *, key=KEY, header=None, payload_json=None, header_json=None):
    def raw(value):
        return value if type(value) is bytes else value.encode("utf-8")
    header_json = (json.dumps(header or {"alg": "HS256", "typ": "JWT"},
                              separators=(",", ":")) if header_json is None else header_json)
    payload_json = json.dumps(claims, separators=(",", ":")) if payload_json is None else payload_json
    encoded = _base64(raw(header_json)) + "." + _base64(raw(payload_json))
    return encoded + "." + _base64(hmac.digest(key, encoded.encode("ascii"), "sha256"))


class PasskeyAssertionTests(unittest.TestCase):
    def setUp(self):
        self.verifier = PasskeyRequestVerifier(
            key=KEY, oidc_issuer=ISSUER, origin=ORIGIN, clock=lambda: NOW,
        )
        self.context = fixture_context()

    def accepted(self, claims=None, *, action="register", body=None, context=None, verifier=None):
        body = fixture_body(action) if body is None else body
        claims = fixture_claims(action, body=body) if claims is None else claims
        return (verifier or self.verifier).verify(
            sign_assertion(claims), action=action, body=body,
            context=self.context if context is None else context,
        )

    def rejected(self, token=None, *, claims=None, action="register", body=None,
                 context=None, verifier=None):
        body = fixture_body(action) if body is None else body
        token = sign_assertion(fixture_claims() if claims is None else claims) if token is None else token
        with self.assertRaises(OnboardingRejected) as caught:
            (verifier or self.verifier).verify(
                token, action=action, body=body,
                context=self.context if context is None else context,
            )
        error = caught.exception
        self.assertEqual(error.code, "authentication_required")
        self.assertEqual(str(error), "authentication_required")
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)
        for secret in (KEY.decode(), SUBJECT, ISSUER, ORIGIN, str(TENANT),
                       TRIPLE["secret"], SESSION_BINDING, METADATA_SHA256):
            self.assertNotIn(secret, repr(error) + str(error))

    def test_all_three_actions_match_exact_target_body_and_route(self):
        for action in TARGETS:
            actual = self.accepted(action=action)
            self.assertEqual(actual.target, fixture_target(action))
            self.assertEqual(actual.htu, TARGETS[action])
            self.assertEqual(actual.htm, "POST")
            for other in TARGETS:
                if action != other:
                    self.rejected(claims=fixture_claims(action), action=other, body=fixture_body(action))

    def test_original_old_oidc_time_is_preserved_separately_from_fresh_passkey(self):
        actual = self.accepted()
        self.assertEqual(actual.oidc_auth_time, NOW - 86400)
        self.assertEqual(actual.passkey_checked_at, NOW - 10)
        self.assertEqual(actual.passkey_authorized_at, NOW - 5)
        self.assertEqual(actual.passkey_version, 2)
        self.assertFalse(hasattr(actual, "auth_time"))
        self.assertFalse(hasattr(actual, "oidc_amr"))
        self.assertFalse(hasattr(actual, "execution_enabled"))

    def test_result_fields_preserve_purpose_specific_ids_and_metadata_digest(self):
        actual = self.accepted()
        for field in ("authorization_id", "proof_id", "grant_id", "tenant_id",
                      "user_id", "passkey_id", "jti"):
            self.assertEqual(getattr(actual, field), UUID(fixture_claims()[field]))
        self.assertEqual(actual.sub, SUBJECT)
        self.assertEqual(actual.authorization_kind, AUTHORIZATION_KIND)
        self.assertEqual(actual.metadata_sha256, METADATA_SHA256)
        # The signed metadata digest is opaque, not recomputed from a target.
        self.assertEqual(self.accepted(fixture_claims(metadata_sha256="ef" * 32)).metadata_sha256, "ef" * 32)

    def test_verification_is_repeatable_and_does_not_consume_or_promise_replay_protection(self):
        token = sign_assertion(fixture_claims())
        first = self.verifier.verify(token, action="register", body=fixture_body(), context=self.context)
        second = self.verifier.verify(token, action="register", body=fixture_body(), context=self.context)
        self.assertEqual(first.authorization_id, second.authorization_id)
        for name in ("consume", "apply", "begin", "transport"):
            self.assertFalse(hasattr(self.verifier, name))

    def test_old_and_new_assertions_and_verifiers_are_not_inheritance_compatible(self):
        actual = self.accepted()
        self.assertIsInstance(actual, PasskeyActionAssertion)
        self.assertNotIsInstance(actual, ActionAssertion)
        self.assertNotIsInstance(self.verifier, RequestVerifier)
        old = RequestVerifier(key=KEY, oidc_issuer=ISSUER, clock=lambda: NOW)
        with self.assertRaises(OnboardingRejected):
            old.verify(sign_assertion(fixture_claims()), action="register", body=fixture_body())
        self.rejected(old_sign(old_claims(body=fixture_body()), key=KEY))
        # Changing the audience alone cannot bridge the two exact claim sets.
        self.rejected(old_sign(old_claims(body=fixture_body(), aud=AUDIENCE), key=KEY))
        self.rejected(claims=fixture_claims(aud="investalo-credentials"))

    def test_exact_claim_set_excludes_fabricated_oidc_mfa_and_other_extensions(self):
        claims = fixture_claims()
        for field in claims:
            self.rejected(claims={name: value for name, value in claims.items() if name != field})
        for field, value in (("oidc_amr", ["mfa"]), ("amr", ["mfa"]),
                             ("step_up_started_at", NOW - 20), ("role", "owner")):
            self.rejected(claims={**claims, field: value})

    def test_dedicated_issuer_audience_scope_and_method_are_exact_strings(self):
        for field, values in {
            "iss": ["other-bff", None, ["investalo-bff"]],
            "aud": ["investalo-credentials", [AUDIENCE], AUDIENCE + " "],
            "authorization_kind": ["passkey-proof/1", None, 1],
            "htm": ["GET", "post", None],
            "htu": [TARGETS["register"] + "/", TARGETS["register"] + "?q=1", None],
        }.items():
            for value in values:
                self.rejected(claims=fixture_claims(**{field: value}))

    def test_every_actor_and_session_context_field_is_bound(self):
        changes = {
            "tenant_id": UUID(int=999), "user_id": UUID(int=998), "subject": "other-actor",
            "auth_epoch": 3, "oidc_auth_time": NOW - 86401,
            "session_binding": "12" * 32, "session_expires_at": NOW + 601,
        }
        for field, value in changes.items():
            self.rejected(context=fixture_context(**{field: value}))
        for invalid in ({}, object(), self.verifier, "untrusted"):
            self.rejected(context=invalid)
        with self.assertRaises(TypeError):
            self.verifier.verify(sign_assertion(fixture_claims()), action="register", body=fixture_body())

    def test_configured_oidc_issuer_origin_and_rp_are_exact(self):
        for field, values in {
            "oidc_iss": [ISSUER + "/", "https://other.fixture.invalid", None],
            "origin": [ORIGIN + "/", "https://cockpit.fixture.invalid", None],
            "rp_id": ["other.fixture.invalid", "COCKPIT.fixture.invalid",
                      "cockpit.fixture.invalid:8443", None],
        }.items():
            for value in values:
                self.rejected(claims=fixture_claims(**{field: value}))

    def test_configured_origins_reject_noncanonical_https_dns_forms(self):
        bad = (
            None, [], "", "http://identity.fixture.invalid", "https://",
            ISSUER + "/", ISSUER + "/path", ISSUER + "?q=1", ISSUER + "#fragment",
            ISSUER + ":443", ISSUER + ":0443", ISSUER + ":08443", ISSUER + ":0",
            ISSUER + ":", "https://IDENTITY.fixture.invalid", "HTTPS://identity.fixture.invalid",
            "https://user@identity.fixture.invalid", "https://user:pass@identity.fixture.invalid",
            "https://identity.fixture.invalid.", "https://identity", "https://127.0.0.1",
            "https://[::1]", "https://127.000.000.001", "https://0x7f.0.0.1",
            "https://bad_name.fixture.invalid", "https://-bad.fixture.invalid",
            "https://bad-.fixture.invalid", "https://dömain.fixture.invalid",
            " https://identity.fixture.invalid", "https://identity.fixture.invalid\n",
        )
        for field in ("oidc_issuer", "origin"):
            for value in bad:
                args = {"key": KEY, "oidc_issuer": ISSUER, "origin": ORIGIN, "clock": lambda: NOW, field: value}
                with self.assertRaises(OnboardingRejected) as caught:
                    PasskeyRequestVerifier(**args)
                self.assertEqual(str(caught.exception), "invalid_context")
                self.assertIsNone(caught.exception.__cause__)
        for origin in ("https://fixture.invalid", "https://cockpit.fixture.invalid:65535"):
            PasskeyRequestVerifier(key=KEY, oidc_issuer=ISSUER, origin=origin, clock=lambda: NOW)

    def test_uuid_claims_and_targets_require_canonical_lowercase_strings(self):
        for field in ("authorization_id", "proof_id", "grant_id", "tenant_id",
                      "user_id", "passkey_id", "jti"):
            for value in (None, 1, "", str(UUID(int=10)).replace("-", ""),
                          "ABCDEFAB-1234-5678-90AB-ABCDEFABCDEF", "{"+str(TENANT)+"}"):
                self.rejected(claims=fixture_claims(**{field: value}))
        for field in ("platform_account_id", "connection_id"):
            for value in (None, 1, "", "{"+ACCOUNT+"}", ACCOUNT.replace("-", "")):
                self.rejected(claims=fixture_claims(target=fixture_target(**{field: value})))

    def test_authorization_proof_and_grant_ids_must_be_distinct(self):
        claims = fixture_claims()
        for first, second in (("authorization_id", "proof_id"),
                              ("authorization_id", "grant_id"), ("proof_id", "grant_id")):
            self.rejected(claims={**claims, first: claims[second]})

    def test_all_integer_claims_reject_bool_float_string_and_safeinteger_overflow(self):
        fields = ("auth_epoch", "oidc_auth_time", "session_expires_at", "passkey_version",
                  "passkey_started_at", "passkey_checked_at", "passkey_authorized_at",
                  "authorization_expires_at", "iat", "exp")
        for field in fields:
            for value in (True, False, 1.0, "1", None, -1, MAX_SAFE_INTEGER + 1):
                self.rejected(claims=fixture_claims(**{field: value}))
        self.accepted(fixture_claims(auth_epoch=MAX_SAFE_INTEGER),
                      context=fixture_context(auth_epoch=MAX_SAFE_INTEGER))
        self.rejected(claims=fixture_claims(passkey_version=1))
        self.accepted(fixture_claims(passkey_version=MAX_SAFE_INTEGER))

    def test_auth_epoch_zero_and_old_positive_oidc_time_are_valid(self):
        self.accepted(fixture_claims(auth_epoch=0, oidc_auth_time=1),
                      context=fixture_context(auth_epoch=0, oidc_auth_time=1))
        self.rejected(claims=fixture_claims(oidc_auth_time=0))
        self.accepted(fixture_claims(oidc_auth_time=NOW + 5),
                      context=fixture_context(oidc_auth_time=NOW + 5))
        self.rejected(claims=fixture_claims(oidc_auth_time=NOW + 6),
                      context=fixture_context(oidc_auth_time=NOW + 6))

    def test_passkey_started_checked_authorized_and_issue_order_is_monotonic(self):
        for changes in (
            {"passkey_started_at": NOW - 9}, {"passkey_checked_at": NOW - 16},
            {"passkey_checked_at": NOW - 4}, {"passkey_authorized_at": NOW - 11},
            {"passkey_authorized_at": NOW + 1}, {"iat": NOW - 6},
            {"passkey_started_at": 0},
        ):
            self.rejected(claims=fixture_claims(**changes))
        self.accepted(fixture_claims(passkey_started_at=NOW, passkey_checked_at=NOW,
                                    passkey_authorized_at=NOW))

    def test_started_and_checked_have_separate_strict_freshness_windows(self):
        self.accepted(fixture_claims(passkey_started_at=NOW - 300))
        self.rejected(claims=fixture_claims(passkey_started_at=NOW - 301))
        accepted = fixture_claims(passkey_started_at=NOW - 300, passkey_checked_at=NOW - 119,
                                  passkey_authorized_at=NOW - 119,
                                  authorization_expires_at=NOW + 1, exp=NOW + 1)
        self.accepted(accepted)
        # A checked_at exactly now-120 leaves no positive receipt lifetime.
        self.rejected(claims={**accepted, "passkey_checked_at": NOW - 120,
                              "passkey_authorized_at": NOW - 120})
        self.rejected(claims=fixture_claims(passkey_checked_at=NOW + 1,
                                          passkey_authorized_at=NOW + 1, iat=NOW + 1))

    def test_issued_time_allows_only_bounded_clock_skew(self):
        self.accepted(fixture_claims(iat=NOW + 5, exp=NOW + 65))
        self.rejected(claims=fixture_claims(iat=NOW + 6))
        self.rejected(claims=fixture_claims(iat=NOW - 61, exp=NOW + 1,
                                          passkey_started_at=NOW - 100,
                                          passkey_checked_at=NOW - 80,
                                          passkey_authorized_at=NOW - 62,
                                          authorization_expires_at=NOW + 20))
        self.accepted(fixture_claims(iat=NOW - 59, exp=NOW + 1,
                                     passkey_started_at=NOW - 100,
                                     passkey_checked_at=NOW - 80,
                                     passkey_authorized_at=NOW - 60,
                                     authorization_expires_at=NOW + 20))

    def test_token_expiry_is_bounded_by_issue_and_authorization_expiry(self):
        for changes in ({"exp": NOW}, {"exp": NOW + 61},
                        {"exp": NOW + 60, "authorization_expires_at": NOW + 59}):
            self.rejected(claims=fixture_claims(**changes))
        self.accepted(fixture_claims(exp=NOW + 1))

    def test_receipt_expiry_is_after_authorization_and_bounded_by_checked_time_and_session(self):
        for expiry in (NOW - 5, NOW - 6, NOW + 111):
            self.rejected(claims=fixture_claims(authorization_expires_at=expiry))
        self.accepted(fixture_claims(authorization_expires_at=NOW + 110))
        self.accepted(fixture_claims(session_expires_at=NOW + 60, authorization_expires_at=NOW + 60),
                      context=fixture_context(session_expires_at=NOW + 60))
        self.rejected(claims=fixture_claims(session_expires_at=NOW + 59),
                      context=fixture_context(session_expires_at=NOW + 59))
        self.rejected(claims=fixture_claims(session_expires_at=NOW),
                      context=fixture_context(session_expires_at=NOW))

    def test_lowercase_hex_digests_are_exact_and_body_hash_binds_raw_bytes(self):
        for field in ("session_binding", "metadata_sha256", "body_sha256"):
            for value in (None, 1, "", "ab" * 31, "ab" * 33, "AB" * 32, "zz" * 32):
                self.rejected(claims=fixture_claims(**{field: value}))
        self.rejected(claims=fixture_claims(body_sha256="12" * 32))
        body = fixture_body()
        self.rejected(claims=fixture_claims(), body=body + b" ")
        # Valid JSON need not use one serializer. Signature binds exact bytes.
        spaced = json.dumps(json.loads(body), indent=1).encode()
        self.accepted(fixture_claims(body=spaced), body=spaced)

    def test_target_rejects_missing_unknown_action_and_extra_fields(self):
        target = fixture_target()
        for changed in (None, [], {}, {**target, "action": "revoke"},
                        {**target, "extra": 1}, {**target, "expected_revision": 1},
                        {**target, "expected_storage": 1}):
            self.rejected(claims={**fixture_claims(), "target": changed})
        for field in target:
            self.rejected(claims=fixture_claims(target={k: v for k, v in target.items() if k != field}))

    def test_target_cas_versions_obey_resulting_javascript_safeinteger_bounds(self):
        for action in ("replace", "revoke"):
            for field in ("expected_revision", "expected_storage"):
                for value in (True, False, 1.0, 0, -1, "1", None, MAX_SAFE_INTEGER + 1):
                    target = fixture_target(action, **{field: value})
                    self.rejected(claims=fixture_claims(action, target=target),
                                  action=action, body=fixture_body(action))
            target = fixture_target(action, expected_revision=MAX_SAFE_INTEGER - 1,
                                    expected_storage=MAX_SAFE_INTEGER - 1)
            body = fixture_body(action, target=target)
            self.accepted(fixture_claims(action, body=body, target=target), action=action, body=body)
            for field in ("expected_storage",) + (("expected_revision",) if action == "replace" else ()):
                target = fixture_target(action, **{field: MAX_SAFE_INTEGER})
                body = fixture_body(action, target=target)
                self.rejected(claims=fixture_claims(action, body=body, target=target), action=action, body=body)
        target = fixture_target("revoke", expected_revision=MAX_SAFE_INTEGER)
        body = fixture_body("revoke", target=target)
        self.accepted(fixture_claims("revoke", body=body, target=target), action="revoke", body=body)

    def test_body_requires_exact_fields_and_matching_target_values(self):
        for action in TARGETS:
            original = json.loads(fixture_body(action))
            changes = [{**original, "action": action}, {**original, "extra": 1},
                       {**original, "connection_id": str(UUID(int=999))},
                       {**original, "platform_account_id": str(UUID(int=998))}]
            changes += [{k: v for k, v in original.items() if k != field} for field in original]
            if action == "revoke":
                changes.append({**original, "credentials": TRIPLE})
            else:
                changes += [{**original, "credentials": value}
                            for value in (None, [], {}, {**TRIPLE, "extra": "value"})]
            if action != "register":
                changes += [{**original, field: value}
                            for field in ("expected_revision", "expected_storage")
                            for value in (True, float(original[field]), original[field] + 1)]
            for changed in changes:
                body = json.dumps(changed).encode()
                self.rejected(claims=fixture_claims(action, body=body), action=action, body=body)

    def test_body_requires_duplicate_free_utf8_json_at_every_level(self):
        body = fixture_body().decode()
        raw_claims = json.dumps(fixture_claims(), separators=(",", ":"))
        for raw in (
            body[:-1] + ',"connection_id":"' + CONNECTION + '"}',
            body.replace('"api_key":"synthetic-key"', '"api_key":"synthetic-key","api_key":"synthetic-key"'),
            body.replace('"api_key":"synthetic-key"', '"api_key":"synthetic-key","api_\\u006bey":"synthetic-key"'),
            body[:-1] + ',"__proto__":{}}', body + "garbage", "null", "[]", "1",
            body.replace('"synthetic-key"', "NaN"),
        ):
            raw = raw.encode()
            self.rejected(claims=fixture_claims(body=raw), body=raw)
        for raw in (body.encode("utf-16"), body.encode("utf-32"), b"\xff", b"\xef\xbb\xbf" + body.encode()):
            self.rejected(claims=fixture_claims(body=raw), body=raw)
        self.rejected(sign_assertion(fixture_claims(), payload_json=raw_claims.encode("utf-16")))
        self.rejected(sign_assertion(fixture_claims(), header_json=b'\xff'))

    def test_broker_strings_require_wellformed_no_unicode_controls(self):
        for field in TRIPLE:
            for value in ("", None, True, "x\n", "x\x7f", "x\u0085",
                          "x\u200b", "x\u202e", "x\ud800"):
                # Escaped lone surrogates can be valid JSON but invalid text.
                body = json.dumps(json.loads(fixture_body()) | {"credentials": TRIPLE | {field: value}}).encode()
                self.rejected(claims=fixture_claims(body=body), body=body)

    def test_broker_string_limits_count_utf8_bytes_without_trimming(self):
        for field, maximum in (("api_key", 256), ("secret", 1024), ("passphrase", 256)):
            for value in ("x" * maximum, "é" * (maximum // 2), " "):
                body = fixture_body(triple=TRIPLE | {field: value})
                self.accepted(fixture_claims(body=body), body=body)
            for value in ("x" * (maximum + 1), "é" * (maximum // 2 + 1)):
                body = fixture_body(triple=TRIPLE | {field: value})
                self.rejected(claims=fixture_claims(body=body), body=body)

    def test_opaque_subject_limits_count_utf8_bytes_and_reject_unicode_controls(self):
        for value in ("x" * 255, "é" * 127, " "):
            self.accepted(fixture_claims(sub=value), context=fixture_context(subject=value))
        for value in ("", None, 1, "x" * 256, "é" * 128, "x\x7f",
                      "x\u0085", "x\u200b", "x\ud800"):
            self.rejected(claims=fixture_claims(sub=value))

    def test_body_type_length_and_action_type_fail_closed(self):
        for body in ("body", bytearray(fixture_body()), b"", b"x" * (MAX_BODY_BYTES + 1), 1):
            self.rejected(body=body)
        for action in (None, True, 1, "REGISTER", "../register", "withdraw"):
            self.rejected(action=action)
        with self.assertRaises(OnboardingRejected):
            self.verifier.verify(sign_assertion(fixture_claims()), action="register",
                                 body=None, context=self.context)

    def test_body_maximum_boundary_accepts_whitespace_only_as_signed_bytes(self):
        body = fixture_body()
        padded = body + b" " * (MAX_BODY_BYTES - len(body))
        self.accepted(fixture_claims(body=padded), body=padded)
        too_large = padded + b" "
        self.rejected(claims=fixture_claims(body=too_large), body=too_large)

    def test_token_types_length_structure_and_base64_canonicality_fail_closed(self):
        for token in (1, b"token", "", "a.b", "a.b.c.d", "a.b.", "x" * 8193):
            self.rejected(token)
        token = sign_assertion(fixture_claims())
        parts = token.split(".")
        for at in range(3):
            changed = parts.copy()
            changed[at] += "="
            self.rejected(".".join(changed))
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        changed = parts.copy()
        changed[2] = changed[2][:-1] + alphabet[alphabet.index(changed[2][-1]) | 1]
        self.assertNotEqual(changed, parts)
        self.rejected(".".join(changed))
        with self.assertRaises(OnboardingRejected):
            self.verifier.verify(None, action="register", body=fixture_body(), context=self.context)

    def test_header_algorithm_and_key_are_dedicated_and_exact(self):
        for header in ({"alg": "none", "typ": "JWT"}, {"alg": "HS384", "typ": "JWT"},
                       {"alg": "HS256"}, {"alg": "HS256", "typ": "other"},
                       {"alg": "HS256", "typ": "JWT", "kid": "untrusted"}):
            self.rejected(sign_assertion(fixture_claims(), header=header))
        self.rejected(sign_assertion(fixture_claims(), key=b"unrelated-signing-key" * 2))
        parts = sign_assertion(fixture_claims()).split(".")
        parts[1] = _base64(json.dumps(fixture_claims(sub="changed")).encode())
        self.rejected(".".join(parts))

    def test_duplicate_claim_and_header_names_and_nonobject_json_rejected(self):
        claims = fixture_claims()
        raw = json.dumps(claims, separators=(",", ":"))
        for duplicate in (raw[:-1] + ',"aud":"' + AUDIENCE + '"}',
                          raw[:-1] + ',"a\\u0075d":"' + AUDIENCE + '"}'):
            self.rejected(sign_assertion(claims, payload_json=duplicate))
        self.rejected(sign_assertion(claims, header_json='{"alg":"HS256","alg":"HS256","typ":"JWT"}'))
        for raw in ("null", "[]", "1", '{"auth_epoch":NaN}', '{"auth_epoch":Infinity}'):
            self.rejected(sign_assertion(claims, payload_json=raw))

    def test_context_constructor_validates_private_values_and_static_errors(self):
        for field, values in {
            "tenant_id": [str(TENANT), None], "user_id": [str(USER), None],
            "subject": ["", "x\u200b", "é" * 128],
            "auth_epoch": [True, -1, MAX_SAFE_INTEGER + 1],
            "oidc_auth_time": [True, 0, 1.0, MAX_SAFE_INTEGER + 1],
            "session_binding": ["AB" * 32, None, "ab" * 31],
            "session_expires_at": [True, 0, 1.0, MAX_SAFE_INTEGER + 1],
        }.items():
            for value in values:
                with self.assertRaises(OnboardingRejected) as caught:
                    fixture_context(**{field: value})
                self.assertEqual(str(caught.exception), "invalid_context")
                self.assertIsNone(caught.exception.__cause__)

    def test_constructor_rejects_weak_nonbytes_keys_and_noncallable_clocks(self):
        for key in (None, KEY.decode(), bytearray(KEY), b"x" * 31, b"x" * 129):
            with self.assertRaises(OnboardingRejected) as caught:
                PasskeyRequestVerifier(key=key, oidc_issuer=ISSUER, origin=ORIGIN, clock=lambda: NOW)
            self.assertEqual(str(caught.exception), "invalid_context")
        for clock in (None, 1, "clock"):
            with self.assertRaises(OnboardingRejected):
                PasskeyRequestVerifier(key=KEY, oidc_issuer=ISSUER, origin=ORIGIN, clock=clock)
        for size in (32, 128):
            PasskeyRequestVerifier(key=b"x" * size, oidc_issuer=ISSUER, origin=ORIGIN, clock=lambda: NOW)

    def test_clock_errors_and_noninteger_out_of_bounds_actual_times_are_redacted(self):
        def failed_clock():
            raise RuntimeError(TRIPLE["secret"])
        for clock in (failed_clock, lambda: True, lambda: 1.0, lambda: float(NOW),
                      lambda: None, lambda: 0, lambda: MAX_SAFE_INTEGER - 299,
                      lambda: MAX_SAFE_INTEGER + 1):
            verifier = PasskeyRequestVerifier(key=KEY, oidc_issuer=ISSUER, origin=ORIGIN, clock=clock)
            self.rejected(verifier=verifier)

    def test_private_objects_are_redacted_immutable_and_nonserializing(self):
        actual = self.accepted()
        for private in (actual, self.context, self.verifier):
            for secret in (SUBJECT, KEY.decode(), TRIPLE["secret"], str(TENANT),
                           ISSUER, ORIGIN, SESSION_BINDING, METADATA_SHA256):
                self.assertNotIn(secret, str(private) + repr(private))
            self.assertFalse(hasattr(private, "__dict__"))
            self.assertFalse(hasattr(private, "public"))
            with self.assertRaises(AttributeError):
                private.extra = "changed"
            for serialize in (pickle.dumps, dataclasses.asdict, json.dumps):
                with self.assertRaises(TypeError):
                    serialize(private)
        self.assertIsInstance(actual.target, MappingProxyType)
        with self.assertRaises(TypeError):
            actual.target["connection_id"] = "changed"
        with self.assertRaises(AttributeError):
            actual.auth_epoch = 10
        self.assertFalse(hasattr(actual, "credentials"))
        self.assertFalse(hasattr(actual, "body"))


if __name__ == "__main__":
    unittest.main()
