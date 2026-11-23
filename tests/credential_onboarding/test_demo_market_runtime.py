"""Original source/store ports, real AEAD/files/dispatcher; synthetic actor/native replies."""
import base64
from contextlib import ExitStack
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from investalo_bitget import ReadResponse
from investalo_bitget.futures_demo import DemoRejected
from investalo_credential_store.demo_market_runtime import DemoMarketTestRuntime, MarketTestState, DOMAINS, TARGETS, validate_market_result
from investalo_credential_store.demo_account_sync import CONTEXT
from investalo_credential_store.demo_trading_provider import SealedDemoTradingProvider
from investalo_credential_store.request_assertion import OnboardingRejected
import test_demo_account_sync as fixture
import test_private_asgi as asgi_fixture
import test_private_http as http_fixture
REAL_SLEEP = time.sleep


class MarketRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.DemoAccountTests(); self.f.setUp(); self.f.btc_test()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "state"; self.root.mkdir(mode=0o700)
        for name in ("registry", "outbox", "consents"): (self.root/name).mkdir(mode=0o700)
        self.stack = ExitStack()
        f = self.f
        def factory(authority, **kwargs):
            class Store:
                def read_snapshot(inner, binding, owner):
                    if f.revoked or binding != f.binding or owner != f.owner: raise OnboardingRejected("access_denied")
                    if time.time_ns()//1_000_000 >= authority.expires_ms: raise OnboardingRejected("access_denied")
                    return f.snapshot
                def provider(inner, spec, *, expected_storage, load_keyring):
                    return SealedDemoTradingProvider(spec, expected_storage=expected_storage,
                        read_snapshot=inner.read_snapshot, load_keyring=load_keyring, expires_ms=authority.expires_ms)
            return Store()
        self.stack.enter_context(patch("investalo_credential_store.demo_account_sync.DemoTradingCredentialStore", side_effect=factory))
        self.stack.enter_context(patch("investalo_credential_store.demo_market_runtime.DemoTradingCredentialStore", side_effect=factory))
        self.stack.enter_context(patch("investalo_credential_store.demo_market_runtime.time.sleep"))
        self.posts, self.details, self.sent_at, self.oid = [], 0, None, None
        self.fail_send = False
        original = f.native.transport
        def native(packet):
            if packet.axis == "positions" and self.posts:
                return self.reply([dict(symbol="BTCUSDT",marginCoin="USDT",holdSide="long",
                    marginMode="isolated",posMode="one_way_mode",leverage="2",total="0.0003",available="0.0003",locked="0")])
            return original(packet)
        f.native.transport = native
        self.runtime = DemoMarketTestRuntime(f.reader, root=self.root, order_transport=self.order)
        self.target = {k:v for k,v in f.target.items() if k != "inspection"}
        self.prepared = None

    def tearDown(self):
        self.runtime.state.close(); self.stack.close(); self.tmp.cleanup()

    def reply(self, data):
        return ReadResponse(200,json.dumps(dict(code="00000",requestTime=time.time_ns()//1_000_000,data=data)).encode())

    def token(self, action, body, **changes):
        context = self.f.context
        claims = {k: str(getattr(context,k)) if type(getattr(context,k)) is UUID else getattr(context,k) for k in CONTEXT}
        now = int(time.time())
        kind,audience = DOMAINS[action]
        claims.update(kind=kind,aud=audience,htu=TARGETS[action],htm="POST",
            oidc_issuer=self.f.config["oidc_issuer"],origin=self.f.config["origin"],iat=now,exp=now+15,
            jti=str(uuid4()),body_sha256=hashlib.sha256(body).hexdigest())
        claims.update(changes)
        enc=lambda v:base64.urlsafe_b64encode(v).rstrip(b"=").decode()
        a,b=enc(b'{"alg":"HS256","typ":"JWT"}'),enc(json.dumps(claims).encode())
        return a+"."+b+"."+enc(hmac.digest(fixture.KEY,(a+"."+b).encode(),"sha256"))

    def call(self, action, request, **claims):
        body=json.dumps(request,separators=(",",":")).encode()
        self.f.native.last = None  # skip only fixture wall-clock pacing; native production guards remain
        return self.runtime(self.f.context,action,self.token(action,body,**claims),body)

    def prepare(self):
        self.prepared=self.call("market_prepare",self.target)
        return self.prepared

    def order(self, packet):
        packet.consume()
        if packet.method=="POST":
            raw=json.loads(packet.body)
            self.posts.append(raw);self.oid=raw["clientOid"];self.sent_at=int(packet.headers["ACCESS-TIMESTAMP"])
            self.assertNotIn("price",raw);self.assertNotIn("force",raw)
            self.assertIn('"kind":"dispatch"',(self.root/"outbox"/"commands.jsonl").read_text())
            self.assertEqual(len(list((self.root/"consents").iterdir())),1)
            if self.fail_send: raise TimeoutError()
            return self.reply(dict(clientOid=self.oid,orderId="123"))
        self.details+=1
        return self.reply(dict(symbol="BTCUSDT",clientOid=self.oid,orderId="123",marginCoin="USDT",
            marginMode="isolated",posMode="one_way_mode",posSide="net",leverage="2",size="0.0003",
            orderType="market",side="buy",reduceOnly="NO",state="filled",baseVolume="0.0003",
            priceAvg="70000",fee="-0.01",cTime=str(self.sent_at),uTime=str(time.time_ns()//1_000_000)))

    def test_original_reader_to_durable_submit_observe_restore_and_no_resend(self):
        prepared=self.prepare()
        self.assertEqual(validate_market_result("market_prepare",prepared),prepared)
        self.assertFalse(self.posts)
        status=self.call("market_submit",prepared["consent_request"])
        self.assertEqual(status["state"],"acknowledged");self.assertIsNone(status["filled_quantity_btc"])
        self.runtime.state.close()
        self.runtime=DemoMarketTestRuntime(self.f.reader,root=self.root,order_transport=self.order)
        observed=self.call("market_observe",{**self.target,"command_id":"latest"})
        self.assertEqual(validate_market_result("market_observe",observed),observed)
        self.assertEqual((observed["state"],observed["filled_quantity_btc"],observed["average_price_usdt"]),("filled","0.0003","70000"))
        self.assertTrue(observed["position_matched"])
        for action,body in (("market_submit",prepared["consent_request"]),("market_prepare",self.target)):
            with self.assertRaises(OnboardingRejected):self.call(action,body)
        self.assertEqual(len(self.posts),1)

    def test_unknown_send_retained_and_get_only_recovery(self):
        p=self.prepare();self.fail_send=True
        status=self.call("market_submit",p["consent_request"])
        self.assertEqual(status["state"],"submission_unknown")
        status=self.call("market_observe",{**self.target,"command_id":p["consent_request"]["command_id"]})
        self.assertEqual(status["state"],"filled")
        self.assertEqual((len(self.posts),self.details),(1,1))

    def test_wrong_token_domain_origin_epoch_and_foreign_target_deny_before_native(self):
        for changes in (dict(kind="investalo-demo-account-read/1"),dict(aud="investalo-demo-account-read"),
                        dict(origin="https://foreign.invalid"),dict(auth_epoch=4),dict(exp=True)):
            with self.subTest(changes=changes),self.assertRaises(OnboardingRejected):
                self.call("market_prepare",self.target,**changes)
        with self.assertRaises(OnboardingRejected):
            self.call("market_prepare",{**self.target,"platform_account_id":str(UUID(int=99))})
        self.assertEqual(self.f.sent,[])
        self.assertFalse((self.root/"installation.json").exists())

    def test_open_orders_unknown_other_wallet_fields_and_bad_profile_deny_before_prepare(self):
        for key,value in (("coupon",None),("grant","1"),("available","9999")):
            old=self.f.wallet[0].get(key)
            self.f.wallet[0][key]=value
            with self.subTest(key=key),self.assertRaises(OnboardingRejected):self.prepare()
            self.f.wallet[0][key]=old
        self.assertFalse(self.posts)

    def test_actor_revocation_and_changed_approved_body_prevent_post(self):
        p=self.prepare()
        changed={**p["consent_request"],"intent_sha256":"0"*64}
        with self.assertRaises(OnboardingRejected):self.call("market_submit",changed)
        self.f.revoked=True
        with self.assertRaises(OnboardingRejected):self.call("market_submit",p["consent_request"])
        self.assertFalse(self.posts)

    def test_reading_prepared_journal_does_not_query_or_submit_an_unattempted_order(self):
        p=self.prepare()
        status=self.call("market_observe",{**self.target,"command_id":p["consent_request"]["command_id"]})
        self.assertEqual(status["state"],"prepared")
        self.assertEqual((len(self.posts),self.details),(0,0))

    def test_partial_bootstrap_and_replaced_original_state_deny(self):
        (self.root/"installation.json").write_bytes(b"");(self.root/"installation.json").chmod(0o600)
        with self.assertRaises(OnboardingRejected):self.prepare()
        self.assertFalse(self.posts)

    def test_only_explicit_http_application_exposes_order_routes(self):
        from investalo_credential_store.private_http import _application_targets,DemoMarketTestHTTPApplication,DemoTradingAccountHTTPApplication
        for cls in (DemoMarketTestHTTPApplication,DemoTradingAccountHTTPApplication):
            app=cls(self.f.reader.context,lambda *args:None,enabled=True)
            self.assertEqual("market_submit" in _application_targets(app),cls is DemoMarketTestHTTPApplication)


class MarketASGITests(unittest.TestCase):
    setUpClass = classmethod(asgi_fixture.PrivateASGITests.setUpClass.__func__)
    tearDownClass = classmethod(asgi_fixture.PrivateASGITests.tearDownClass.__func__)
    server_context = asgi_fixture.PrivateASGITests.server_context
    client_context = asgi_fixture.PrivateASGITests.client_context
    exchange = asgi_fixture.PrivateASGITests.exchange
    response = asgi_fixture.PrivateASGITests.response
    server = asgi_fixture.PrivateASGITests.server

    def setUp(self):
        asgi_fixture.PrivateASGITests.setUp(self)
        self.case = MarketRuntimeTests(); self.case.setUp()
        # Real socket acceptance also exercises original UID/group pacing.
        self.sleep_patch = patch("investalo_credential_store.demo_market_runtime.time.sleep", REAL_SLEEP)
        self.sleep_patch.start()
        self.store = self.case.f.reader.context

    def tearDown(self):
        self.sleep_patch.stop()
        self.case.tearDown()

    def wire(self, action, request):
        body = json.dumps(request,separators=(",",":")).encode()
        context = {k: str(getattr(self.case.f.context,k)) if type(getattr(self.case.f.context,k)) is UUID
            else getattr(self.case.f.context,k) for k in CONTEXT}
        encoded = base64.urlsafe_b64encode(json.dumps(context).encode()).rstrip(b"=").decode()
        token = self.case.token(action,body)
        return (f"POST {TARGETS[action]} HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nAuthorization: Bearer {token}\r\n"
            f"X-Investalo-Credential-Context: {encoded}\r\nConnection: close\r\n\r\n").encode()+body

    def test_actual_asgi_mtls_prepare_submit_observe_retains_original_actor_context(self):
        from investalo_credential_store.private_http import DemoMarketTestHTTPApplication
        with self.server(execute=self.case.runtime,application_type=DemoMarketTestHTTPApplication) as service:
            code,data = self.response(self.exchange(service,self.wire("market_prepare",self.case.target)))
            self.assertEqual(code,200)
            code,ack = self.response(self.exchange(service,self.wire("market_submit",data["consent_request"])))
            self.assertEqual(code,200)
            self.assertEqual((code,ack["state"]),(200,"acknowledged"))
            code,result = self.response(self.exchange(service,self.wire("market_observe",{**self.case.target,"command_id":"latest"})))
            self.assertEqual((code,result["state"],result["position_matched"]),(200,"filled",True))
        self.assertEqual(len(self.case.posts),1)
