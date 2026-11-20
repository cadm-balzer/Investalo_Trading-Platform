"""Actual operative native composition with synthetic HTTPS replies only."""
import json
import unittest
from uuid import UUID

from investalo_bitget import Credentials, OwnerContext
from investalo_bitget.transport import ReadResponse
from investalo_credential_store.demo_trading_runtime import (
    configuration, NativeDemoRegistration, SCHEMA, main,
)
from investalo_credential_store.demo_trading_secret import DemoTradingSecretSpec
from investalo_credential_store.request_assertion import OnboardingRejected

NOW = 1_800_000_000_000
CONFIG = dict(schema=SCHEMA, tenant_id=str(UUID(int=1)), user_id=str(UUID(int=2)),
    account_id=str(UUID(int=3)), broker_uid="12345", parent_uid="0", egress_ip="203.0.113.19",
    ip_binding="single_ip",
    origin="https://cockpit.investalo.de", oidc_issuer="https://auth.cockpit.investalo.de",
    created_in_bitget_demo_mode=True, signing_sha256="a"*64, kek_sha256="b"*64,
    client_certificate_sha256="c"*64)


class DemoTradingRuntimeTests(unittest.TestCase):
    def registration(self, *, data=None, at=NOW, transport=None, guard=None, config=None, diagnostic=None, identity_diagnostic=None):
        self.sent = []
        raw = dict(userId="12345", parentId=0, authorities=["coow","cpow","stow"],
                   ips="203.0.113.19")
        raw.update(data or {})
        def reply(request):
            self.sent.append(request)
            return ReadResponse(200, json.dumps(dict(code="00000", msg="success",
                requestTime=at, data=raw)).encode())
        return NativeDemoRegistration(config or CONFIG, guard or (lambda: None),
            transport=transport or reply, milliseconds=lambda: NOW, diagnostic=diagnostic,
            identity_diagnostic=identity_diagnostic)

    def apply(self, registration, **overrides):
        fields = dict(owner=OwnerContext(UUID(int=1), UUID(int=2)), account_id=UUID(int=3),
                      connection_id=UUID(int=4), expires_ms=NOW+30_000)
        fields.update(overrides)
        return registration(Credentials("synthetic-runtime-api", "synthetic-runtime-secret",
                                        "synthetic-runtime-passphrase"), **fields)

    def test_one_fixed_signed_native_get_returns_own_spec(self):
        result = self.apply(self.registration(data={"authorities":["stow","stor","coow","cpow"]}))
        self.assertIs(type(result), DemoTradingSecretSpec)
        self.assertEqual(result.authorities, ("coow","cpow","stor","stow"))
        self.assertEqual(len(self.sent), 1)
        request = self.sent[0]
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.axis, "identity")
        self.assertEqual(request.body, b"")
        self.assertEqual(request.headers["paptrading"], "1")
        self.assertFalse(result.record()["order_execution_enabled"])

    def test_native_drift_never_returns_a_spec_or_retries(self):
        for data in ({"userId":"22222"}, {"parentId":"1"}, {"ips":""},
                     {"ips":"203.0.113.19,203.0.113.20"},
                     {"authorities":["coow","cpow","stow","wwow"]},
                     {"authorities":["coor","cpor","stor"]}, {"accountMode":"UTA"}):
            with self.subTest(data=data):
                with self.assertRaises(OnboardingRejected):
                    self.apply(self.registration(data=data))
                self.assertEqual(len(self.sent), 1)

    def test_stale_or_future_native_clock_denies(self):
        for at in (NOW-5001, NOW+1):
            with self.subTest(at=at), self.assertRaises(OnboardingRejected):
                self.apply(self.registration(at=at))

    def test_explicit_demo_without_binding_accepts_only_empty_native_whitelist(self):
        config = dict(CONFIG, ip_binding="unavailable_in_demo")
        for ips in ("", None):
            with self.subTest(ips=ips):
                self.assertIs(type(self.apply(self.registration(config=config, data={"ips":ips}))),
                              DemoTradingSecretSpec)
        with self.assertRaises(OnboardingRejected):
            self.apply(self.registration(config=config))  # A new whitelist is configuration drift.

    def test_wrong_scope_denies_before_http(self):
        for fields in ({"account_id":UUID(int=8)}, {"owner":OwnerContext(UUID(int=9),UUID(int=2))},
                       {"expires_ms":NOW}, {"expires_ms":NOW+60_001}):
            with self.subTest(fields=fields):
                with self.assertRaises(OnboardingRejected):
                    self.apply(self.registration(), **fields)
                self.assertEqual(self.sent, [])

    def test_failed_send_consumes_interval_without_retry(self):
        count = []
        def failure(_):
            count.append(True)
            raise RuntimeError("private broker output")
        registration = self.registration(transport=failure)
        for _ in range(2):
            with self.assertRaises(OnboardingRejected) as error:
                self.apply(registration)
            self.assertNotIn("private broker output", str(error.exception))
        self.assertEqual(len(count), 1)

    def test_private_diagnostic_identifies_binding_and_rights_without_native_fields(self):
        for data,stage,reason in (
            ({"userId":"22222"}, "binding", "uid_mismatch"),
            ({"authorities":["coor","cpor","stor"]}, "identity", "permission_rejected"),
        ):
            records=[]
            registration=self.registration(data=data,diagnostic=records.append)
            with self.assertRaises(OnboardingRejected):
                self.apply(registration)
            self.assertEqual(len(self.sent),1)
            self.assertEqual(len(records),1)
            self.assertEqual(records[0]["stage"],stage)
            self.assertEqual(records[0]["reason"],reason)
            self.assertEqual(set(records[0]),{
                "schema","checked_ms","stage","outcome","reason","http_status","provider_code",
                "authorities","missing_required","unexpected_count","uid_matches","parent_matches"})
            wire=json.dumps(records[0])
            self.assertNotIn("22222",wire)
            self.assertNotIn("synthetic-runtime",wire)

    def test_unknown_authority_bytes_never_enter_diagnostics_or_gain_acceptance(self):
        records=[]
        with self.assertRaises(OnboardingRejected):
            self.apply(self.registration(
                data={"authorities":["coow","cpow","stow","private-secret-value"]},
                diagnostic=records.append))
        self.assertEqual(records[0]["unexpected_count"],1)
        self.assertEqual(records[0]["authorities"],["coow","cpow","stow"])
        self.assertNotIn("private-secret-value",json.dumps(records))
        self.assertEqual(len(self.sent),1)

    def test_private_identity_evidence_never_authorizes_a_foreign_uid_or_forbidden_rights(self):
        identities=[]
        with self.assertRaises(OnboardingRejected):
            self.apply(self.registration(data={"userId":"22222"},identity_diagnostic=identities.append))
        self.assertEqual(len(identities),1)
        self.assertEqual(identities[0]["broker_uid"],"22222")
        self.assertFalse(identities[0]["registration_authorized"])
        self.assertNotIn("synthetic-runtime",json.dumps(identities))
        identities.clear()
        with self.assertRaises(OnboardingRejected):
            self.apply(self.registration(
                data={"authorities":["coow","cpow","stow","smow"]},
                identity_diagnostic=identities.append))
        self.assertEqual(identities,[])
        with self.assertRaises(OnboardingRejected):
            self.apply(self.registration(at=NOW-5001,identity_diagnostic=identities.append))
        self.assertEqual(identities,[])

    def test_diagnostic_failure_cannot_turn_a_rejection_into_acceptance_or_retry(self):
        def broken(_):
            raise OSError("private diagnostic failure")
        with self.assertRaises(OnboardingRejected):
            self.apply(self.registration(data={"userId":"22222"},diagnostic=broken))
        self.assertEqual(len(self.sent),1)

    def test_configuration_drift_after_send_denies(self):
        calls = []
        def guard():
            calls.append(True)
            if len(calls) == 2:
                raise ValueError()
        with self.assertRaises(OnboardingRejected):
            self.apply(self.registration(guard=guard))
        self.assertEqual(len(self.sent), 1)

    def test_concurrent_native_attempt_denies_without_send(self):
        registration = self.registration()
        registration.lock.acquire()
        try:
            with self.assertRaises(OnboardingRejected):
                self.apply(registration)
            self.assertEqual(self.sent, [])
        finally:
            registration.lock.release()

    def test_operator_config_requires_demo_attestation_and_separate_keys(self):
        for fields in ({"created_in_bitget_demo_mode":False}, {"schema":"old"},
                       {"signing_sha256":"b"*64}, {"origin":"https://other.example"},
                       {"egress_ip":""}, {"unexpected":True}):
            with self.subTest(fields=fields), self.assertRaises(OnboardingRejected):
                configuration(dict(CONFIG, **fields))

    def test_default_launcher_rejects_before_setup(self):
        self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
