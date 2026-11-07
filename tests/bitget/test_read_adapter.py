"""All data/keys are invented fixtures. No account or network access."""
import dataclasses
from decimal import Decimal, localcontext
import json
import pickle
import ssl
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler
from uuid import UUID

from investalo_bitget import (
    AccountBinding, AccountMode, BitgetRejected, ClassicReadClient, Credentials,
    ErrorCode, HTTPSReadTransport, OwnerContext, ProductType, READ_AUTHORITIES,
    ReadResponse, SignedReadRequest, validate_unique_binding,
)
from investalo_bitget import parse
from investalo_bitget.models import uid
from investalo_bitget.signing import FUTURES_PATH, INFO_PATH, SPOT_PATH, hmac_sha256_base64
from investalo_bitget.transport import MAX_RESPONSE_BYTES, _NoRedirect

AT = 1700000000123
IP = "192.0.2.10"
OWNER = OwnerContext(UUID(int=1), UUID(int=2))
OTHER = OwnerContext(UUID(int=1), UUID(int=3))


def response(data, **overrides):
    return ReadResponse(200, json.dumps({
        "code": "00000", "requestTime": AT, "data": data, **overrides,
    }).encode())


def identity(**overrides):
    return {"userId": "123456", "parentId": 0, "ips": IP, "authorities": ["stor", "coor"],
            **overrides}


def binding(**overrides):
    return AccountBinding(**{
        "owner": OWNER, "expected_uid": "123456", "expected_parent_id": "0",
        "expected_egress_ip": IP, **overrides,
    })


class Fixture:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.now = 0

    def __call__(self, request):
        self.calls.append(request)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def tick(self):
        self.now += 2
        return self.now

    def client(self, **options):
        return ClassicReadClient(Credentials("fixture-key", "fixture-secret", "fixture-pass"),
                                 OWNER, transport=self, milliseconds=lambda: AT,
                                 monotonic=self.tick, **options)


class RejectMixin:
    def rejected(self, code, action):
        with self.assertRaises(BitgetRejected) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code.value)
        return caught.exception


class SigningTests(RejectMixin, unittest.TestCase):
    def setUp(self):
        self.credentials = Credentials("fixture-key", "fixture-secret", "fixture-pass")

    def test_rfc4231_and_exact_get_signatures(self):
        self.assertEqual(hmac_sha256_base64(b"\x0b" * 20, b"Hi There"),
                         "sDRMYdjbOFNcqK/OrwvxK4gdwgDJgz2nJuk3bC4yz/c=")
        vectors = (
            (INFO_PATH, (), "fxP6489DsTDeccoAErURJrrwkDcpjSnTMObAZV49bJs="),
            (SPOT_PATH, (("assetType", "all"),), "uKOHPpRstmi0bTcw12GzL6VBvSoLBbID4MaairbhD0g="),
            (FUTURES_PATH, (("productType", "USDT-FUTURES"),),
             "QZ2nx9PVz3B91oQ2jP8hxuAzO9CF356UmHfEHIK9CL0="),
        )
        for path, query, expected in vectors:
            request = SignedReadRequest(self.credentials, path, query, AT)
            self.assertEqual(request.headers["ACCESS-SIGN"], expected)
            self.assertEqual(request.headers["ACCESS-TIMESTAMP"], str(AT))
            self.assertEqual(request.headers["Content-Type"], "application/json")
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.body, b"")
            self.assertTrue(request.url.startswith("https://api.bitget.com/api/v2/"))
            request.validate()

    def test_no_mutation_foreign_url_or_unapproved_query(self):
        invalid = (
            ("https://example.org/api/v2/spot/account/info", (), {}),
            ("/api/v2/spot/trade/place-order", (), {}),
            ("/api/v2/spot/wallet/transfer", (), {}),
            (INFO_PATH, (), {"method": "POST"}),
            (INFO_PATH, (), {"body": b'{"order":"bad"}'}),
            (INFO_PATH, (("redirect", "evil"),), {}),
            (SPOT_PATH, (), {}),
            (FUTURES_PATH, (("productType", "UTA"),), {}),
            (FUTURES_PATH, (("productType", "USDT-FUTURES"), ("x", "y")), {}),
        )
        for path, query, options in invalid:
            self.rejected(ErrorCode.INVALID_REQUEST,
                          lambda: SignedReadRequest(self.credentials, path, query, AT, **options))
        for at in (True, -1, "1700", 10**15):
            self.rejected(ErrorCode.INVALID_REQUEST,
                          lambda: SignedReadRequest(self.credentials, INFO_PATH, (), at))

    def test_incidental_repr_serialization_and_mutation_redacted(self):
        request = SignedReadRequest(self.credentials, INFO_PATH, (), AT)
        for value in (self.credentials, request, request.headers):
            rendered = repr(value) + str(value)
            for secret in ("fixture-key", "fixture-secret", "fixture-pass",
                           request.headers["ACCESS-SIGN"]):
                self.assertNotIn(secret, rendered)
            with self.assertRaises(TypeError):
                pickle.dumps(value)
            with self.assertRaises(TypeError):
                dataclasses.asdict(value)
        with self.assertRaises(AttributeError):
            request.url = "https://evil.test"
        with self.assertRaises(TypeError):
            request.headers["ACCESS-KEY"] = "changed"
        with self.assertRaises(AttributeError):
            request.headers._values = {}

    def test_invalid_credentials_errors_never_echo_values(self):
        for triple in (("", "x", "pass"), ("key\n", "secret", "pass"),
                       ("key", "secret\ud800", "pass"), ("key", "secret", "pass\n"),
                       ("key", None, "pass"), ("key", "x" * 1025, "pass")):
            error = self.rejected(ErrorCode.INVALID_CREDENTIALS, lambda: Credentials(*triple))
            self.assertIsNone(error.__cause__)
            self.assertNotIn("secret", repr(error))


class ParsingTests(RejectMixin, unittest.TestCase):
    def test_read_permissions_known_only_and_classic_shape(self):
        info = parse.identity(response(identity(authorities=sorted(READ_AUTHORITIES))))
        self.assertEqual(set(info.authorities), READ_AUTHORITIES)
        self.assertEqual(info.parent_id, "0")
        self.assertEqual(info.mode_evidence, "declared_classic_and_v2_schema")
        for code in ("stow", "coow", "cpow", "wwow", "wtow", "chow", "taxw", "pllr", "unknown"):
            self.rejected(ErrorCode.PERMISSION_REJECTED,
                          lambda: parse.identity(response(identity(authorities=["stor", code]))))
        for rights in ([], ["stor", "stor"], "stor", [1]):
            self.rejected(ErrorCode.PERMISSION_REJECTED,
                          lambda: parse.identity(response(identity(authorities=rights))))
        for field in ("permType", "permissions", "uid", "accountType", "accountMode"):
            self.rejected(ErrorCode.MODE_UNSUPPORTED,
                          lambda: parse.identity(response(identity(**{field: "classic"}))))

    def test_parent_unknown_is_distinct_from_zero_and_uid_ascii(self):
        self.assertIsNone(parse.identity(response(identity(parentId=None))).parent_id)
        self.assertEqual(parse.identity(response(identity(parentId=456))).parent_id, "456")
        for value in ("1٢", "", 123, "0", "001"):
            self.rejected(ErrorCode.INVALID_RESPONSE, lambda: uid(value))
        for value in ("", False, -1, "٠"):
            self.rejected(ErrorCode.INVALID_RESPONSE,
                          lambda: parse.identity(response(identity(parentId=value))))

    def test_envelope_bounds_duplicate_and_no_raw_provider_message(self):
        error = self.rejected(ErrorCode.PROVIDER_REJECTED,
                              lambda: parse.identity(response({}, code="429", msg="secret-key")))
        self.assertNotIn("secret-key", repr(error))
        self.rejected(ErrorCode.HTTP_FAILURE, lambda: parse.envelope(ReadResponse(429, b"secret")))
        self.rejected(ErrorCode.RESPONSE_TOO_LARGE,
                      lambda: parse.envelope(ReadResponse(200, b"x" * (MAX_RESPONSE_BYTES + 1))))
        for raw in (b'{"code":"00000","code":"bad"}', b'{"data":NaN}', b"\xff",
                    b"[]", b'{"code":"00000","data":[],"requestTime":true}'):
            with self.assertRaises(BitgetRejected):
                parse.envelope(ReadResponse(200, raw))

    def test_decimal_exact_bounds_under_changed_context(self):
        for precision in (6, 28, 60):
            with localcontext() as context:
                context.prec = precision
                self.assertEqual(parse.amount("0.123456789123456789"), Decimal("0.123456789123456789"))
                self.assertEqual(parse.amount("1e30"), Decimal("1e30"))
                for value in ("1000000000000000000000000000000.1",
                              "1000000000000000000000000000000.00000000000000001"):
                    self.rejected(ErrorCode.INVALID_BALANCE, lambda: parse.amount(value))
        for value in ("NaN", "Infinity", "1,000", "١.٢", "1e99", "1e-31", " 1", 1, True, "-0.1"):
            self.rejected(ErrorCode.INVALID_BALANCE, lambda: parse.amount(value))
        self.assertIsNone(parse.amount(None))
        self.assertIsNone(parse.amount(""))
        self.assertEqual(parse.amount("0"), Decimal("0"))

    def test_spot_unknown_zero_case_and_timestamp_provenance(self):
        assets, _ = parse.spot_assets(response([
            {"coin": "usdt", "available": "0", "frozen": "", "uTime": "1695808946"},
            {"coin": "preSPAX", "locked": "1.00000000000001"},
        ]))
        self.assertEqual(assets[0].coin, "usdt")
        self.assertEqual(assets[0].available, Decimal("0"))
        self.assertIsNone(assets[0].frozen)
        self.assertIsNone(assets[0].locked)
        self.assertEqual(assets[0].updated_at_ms, 1695808946)
        self.assertEqual(assets[1].coin, "preSPAX")
        for value in ("١٧٠٠", True, "-1"):
            self.rejected(ErrorCode.INVALID_RESPONSE, lambda: parse.timestamp_ms(value))
        self.rejected(ErrorCode.INVALID_BALANCE, lambda: parse.spot_assets(
            response([{"coin": "USDT", "available": "-1"}])))

    def test_negative_futures_and_equity_not_pnl_double_counted(self):
        accounts, _ = parse.futures_accounts(response([{
            "marginCoin": "USDT", "available": "-2.5", "accountEquity": "-1.5",
            "usdtEquity": "-1.5", "btcEquity": "-0.00002", "unrealizedPL": "-3",
            "isolatedUnrealizedPL": "", "isolatedMargin": None, "assetMode": "union",
            "assetList": [{"coin": "preSPAX", "balance": "-1", "available": "-2"}],
        }]), ProductType.USDT)
        account = accounts[0]
        self.assertEqual(account.account_equity, Decimal("-1.5"))
        self.assertEqual(account.unrealized_pnl, Decimal("-3"))
        self.assertEqual(account.available, Decimal("-2.5"))
        self.assertIsNone(account.isolated_unrealized_pnl)
        self.assertIsNone(account.crossed_margin)
        self.assertEqual(account.assets[0].coin, "preSPAX")
        self.assertEqual(account.asset_mode, "union")
        self.assertFalse(hasattr(account, "combined_equity"))
        for row in ({"marginCoin": "USDT", "assetMode": "uta"},
                    {"marginCoin": "USDT", "locked": "-1"},
                    {"marginCoin": "USDC"}, {"marginCoin": "usdt"}):
            with self.assertRaises(BitgetRejected):
                parse.futures_accounts(response([row]), ProductType.USDT)

    def test_duplicate_and_resource_bound_asset_rows(self):
        for rows in ([{"coin": "BTC"}, {"coin": "BTC"}], [{}],
                     [{"coin": f"C{i}"} for i in range(parse.MAX_ASSETS + 1)]):
            self.rejected(ErrorCode.INVALID_BALANCE, lambda: parse.spot_assets(response(rows)))
        self.rejected(ErrorCode.INVALID_BALANCE, lambda: parse.futures_accounts(
            response([{"marginCoin": "USDT", "assetList": [{"coin": "BTC"}, {"coin": "BTC"}]}]),
            ProductType.USDT))


class ClientTests(RejectMixin, unittest.TestCase):
    def test_onboarding_probe_gates_ip_and_learns_uid_without_binding(self):
        fixture = Fixture(response(identity(userId="777777")))
        learned = fixture.client().probe_identity(OWNER, expected_egress_ip=IP)
        self.assertEqual(learned.user_id, "777777")
        self.assertEqual([call.path for call in fixture.calls], [INFO_PATH])
        new_binding = AccountBinding(OWNER, learned.user_id, learned.parent_id, expected_egress_ip=IP)
        new_binding.validate(OWNER, learned, require_ip=True)
        fixture = Fixture(response(identity()))
        self.rejected(ErrorCode.IP_MISMATCH,
                      lambda: fixture.client().probe_identity(OWNER, expected_egress_ip="192.0.2.99"))
        self.assertEqual(len(fixture.calls), 1)

    def test_default_gate_includes_wrapped_transports_and_empty_whitelist(self):
        fixture = Fixture(response(identity()))
        self.rejected(ErrorCode.IP_GATE_REQUIRED, lambda: fixture.client().read_identity(OWNER))
        self.assertEqual(fixture.calls, [])
        fixture = Fixture(response(identity(ips="")))
        self.rejected(ErrorCode.IP_GATE_REQUIRED,
                      lambda: fixture.client().probe_identity(OWNER, expected_egress_ip=IP))
        fixture = Fixture(response(identity(ips=None)))
        self.rejected(ErrorCode.IP_GATE_REQUIRED,
                      lambda: fixture.client().read_spot(OWNER, binding()))
        self.assertEqual(len(fixture.calls), 1)
        with patch.object(HTTPSReadTransport, "__call__") as network:
            self.rejected(ErrorCode.IP_GATE_REQUIRED, lambda: ClassicReadClient(
                Credentials("fixture-key", "fixture-secret", "fixture-pass"), OWNER,
                transport=HTTPSReadTransport(), require_ip_gate=False))
            network.assert_not_called()

    def test_fixture_opt_out_explicit_and_wallet_binding_still_required(self):
        fixture = Fixture(response(identity(ips=None)))
        info = fixture.client(require_ip_gate=False).read_identity(OWNER)
        self.assertIsNone(info.ip_whitelist)
        fixture = Fixture()
        for value in (None, "not-a-binding", OWNER):
            self.rejected(ErrorCode.CONTEXT_MISMATCH,
                          lambda: fixture.client().read_spot(OWNER, value))
            self.rejected(ErrorCode.CONTEXT_MISMATCH,
                          lambda: fixture.client().read_futures(OWNER, value, ProductType.USDT))
        self.assertEqual(fixture.calls, [])

    def test_owner_and_declared_mode_fail_before_dispatch(self):
        fixture = Fixture()
        client = fixture.client()
        self.rejected(ErrorCode.CONTEXT_MISMATCH, lambda: client.read_spot(OTHER, binding()))
        self.rejected(ErrorCode.CONTEXT_MISMATCH, lambda: client.read_spot(
            OWNER, binding(owner=OTHER)))
        self.rejected(ErrorCode.MODE_UNSUPPORTED,
                      lambda: fixture.client(declared_mode=AccountMode.UTA))
        self.assertEqual(fixture.calls, [])

    def test_fresh_identity_uid_parent_permissions_guard_every_wallet(self):
        cases = (
            (identity(userId="999"), ErrorCode.UID_MISMATCH),
            (identity(parentId=None), ErrorCode.PARENT_MISMATCH),
            (identity(ips="192.0.2.99"), ErrorCode.IP_MISMATCH),
            (identity(authorities=["stor", "wwow"]), ErrorCode.PERMISSION_REJECTED),
        )
        for info, expected in cases:
            fixture = Fixture(response(info))
            self.rejected(expected, lambda: fixture.client().read_spot(OWNER, binding()))
            self.assertEqual([call.path for call in fixture.calls], [INFO_PATH])

    def test_separate_wallets_fresh_info_and_validated_product(self):
        fixture = Fixture(response(identity()), response([{"coin": "USDT", "available": "500"}]),
                          response(identity()), response([{
                              "marginCoin": "USDT", "accountEquity": "100", "unrealizedPL": "20"}]))
        client = fixture.client()
        spot = client.read_spot(OWNER, binding())
        futures = client.read_futures(OWNER, binding(), ProductType.USDT)
        self.assertEqual(spot.wallet_type, "spot")
        self.assertEqual(futures.wallet_type, "futures")
        self.assertEqual(spot.assets[0].available, Decimal("500"))
        self.assertEqual(futures.accounts[0].account_equity, Decimal("100"))
        self.assertFalse(hasattr(client, "total_budget"))
        self.assertEqual([call.path for call in fixture.calls],
                         [INFO_PATH, SPOT_PATH, INFO_PATH, FUTURES_PATH])
        self.assertEqual(fixture.calls[-1].parameters, (("productType", "USDT-FUTURES"),))
        self.rejected(ErrorCode.INVALID_REQUEST,
                      lambda: client.read_futures(OWNER, binding(), "USDT-FUTURES"))
        self.assertEqual(len(fixture.calls), 4)
        self.assertNotIn("500", repr(spot))
        self.assertNotIn("123456", repr(futures.identity))

    def test_no_retry_local_pacing_even_after_failed_call(self):
        fixture = Fixture(ReadResponse(429, b"secret-provider-body"))
        client = fixture.client()
        client._monotonic = lambda: 10
        self.rejected(ErrorCode.HTTP_FAILURE, lambda: client.read_spot(OWNER, binding()))
        self.rejected(ErrorCode.LOCAL_RATE_LIMIT, lambda: client.read_spot(OWNER, binding()))
        self.assertEqual(len(fixture.calls), 1)

    def test_permission_change_after_success_blocks_next_wallet_dispatch(self):
        fixture = Fixture(response(identity()), response([{"coin": "USDT", "available": "5"}]),
                          response(identity(authorities=["stor", "wwow"])))
        client = fixture.client()
        client.read_spot(OWNER, binding())
        self.rejected(ErrorCode.PERMISSION_REJECTED,
                      lambda: client.read_futures(OWNER, binding(), ProductType.USDT))
        self.assertEqual([request.path for request in fixture.calls], [INFO_PATH, SPOT_PATH, INFO_PATH])

    def test_transport_exception_is_static_and_suppressed(self):
        fixture = Fixture(RuntimeError("fixture-secret-provider-error"))
        error = self.rejected(ErrorCode.TRANSPORT_FAILURE,
                              lambda: fixture.client().read_identity(OWNER, binding=binding()))
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)
        self.assertNotIn("fixture-secret", str(error))

    def test_unique_uid_validator_cross_tenant_and_owner(self):
        validate_unique_binding(binding(), (binding(),))
        self.rejected(ErrorCode.ACCOUNT_ALREADY_BOUND,
                      lambda: validate_unique_binding(binding(owner=OTHER), (binding(),)))
        third = OwnerContext(UUID(int=4), UUID(int=2))
        self.rejected(ErrorCode.ACCOUNT_ALREADY_BOUND,
                      lambda: validate_unique_binding(binding(owner=third), (binding(),)))


class HTTPTests(RejectMixin, unittest.TestCase):
    def request(self):
        return SignedReadRequest(Credentials("fixture-key", "fixture-secret", "fixture-pass"),
                                 INFO_PATH, (), AT)

    def test_tls_proxy_timeout_and_response_bound_without_network(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, maximum):
                self.maximum = maximum
                return b"{}"
        returned = Response()
        class Opener:
            def open(self, outgoing, timeout):
                self.outgoing, self.timeout = outgoing, timeout
                return returned
        opener = Opener()
        with patch("investalo_bitget.transport.build_opener", return_value=opener) as build:
            result = HTTPSReadTransport()(self.request())
        handlers = build.call_args.args
        proxy = next(handler for handler in handlers if isinstance(handler, ProxyHandler))
        https = next(handler for handler in handlers if isinstance(handler, HTTPSHandler))
        self.assertEqual(proxy.proxies, {})
        self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(https._context.check_hostname)
        self.assertEqual(https._context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertEqual(opener.outgoing.get_method(), "GET")
        self.assertEqual(opener.timeout, 10)
        self.assertEqual(returned.maximum, MAX_RESPONSE_BYTES + 1)
        self.assertEqual(result.body, b"{}")
        self.assertNotIn("{}", repr(result))

    def test_redirect_and_http_errors_do_not_echo_request(self):
        self.rejected(ErrorCode.REDIRECT_DENIED, lambda: _NoRedirect().redirect_request(
            None, None, 302, "secret", {}, "https://evil.test"))
        class Opener:
            def open(self, *args, **kwargs):
                raise HTTPError("secret-key-url", 429, "secret-pass", {}, None)
        with patch("investalo_bitget.transport.build_opener", return_value=Opener()):
            error = self.rejected(ErrorCode.HTTP_FAILURE, lambda: HTTPSReadTransport()(self.request()))
        self.assertTrue(error.__suppress_context__)
        self.assertIsNone(error.__cause__)
        for timeout in (0, 21, float("inf"), "10"):
            self.rejected(ErrorCode.INVALID_REQUEST, lambda: HTTPSReadTransport(timeout))

    def test_response_cap_enforced_on_transport_not_only_parser(self):
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, maximum):
                return b"x" * maximum
        class Opener:
            def open(self, *args, **kwargs):
                return Response()
        with patch("investalo_bitget.transport.build_opener", return_value=Opener()):
            self.rejected(ErrorCode.RESPONSE_TOO_LARGE, lambda: HTTPSReadTransport()(self.request()))


if __name__ == "__main__":
    unittest.main()
