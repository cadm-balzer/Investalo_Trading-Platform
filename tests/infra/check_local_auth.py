#!/usr/bin/env python3
"""Exercise the TLS/IdP/BFF boundary using only generated test data.

The default stays loopback-only with the local CA. --public-preview explicitly
uses the two approved public development origins and system-trusted TLS.
No token/password output or disabled TLS. Run only after the matching
development identity, snapshot and worker have been provisioned.
"""
from __future__ import annotations

import base64
import argparse
import hashlib
import hmac
from html.parser import HTMLParser
import http.client
import http.cookiejar
import json
from pathlib import Path
import re
import socket
import ssl
import struct
import sys
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import (
    HTTPSHandler, HTTPRedirectHandler, HTTPCookieProcessor, ProxyHandler,
    Request, build_opener,
)
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra/local"
APP = "https://cockpit.local.test:8443"
IDP = "https://auth.cockpit.local.test:8443"
CONTEXT: ssl.SSLContext | None = None
PUBLIC_PREVIEW = False
STEP = "initialize"

class DatasetOptions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.label = ""
        self.options = []
        self.in_script = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "option":
            self.current = dict(attrs).get("value")
            self.label = ""
        elif tag == "script":
            self.in_script = True
            self.scripts.append("")

    def handle_data(self, data):
        if self.current:
            self.label += data
        if self.in_script:
            self.scripts[-1] += data

    def handle_endtag(self, tag):
        if tag == "option":
            if self.current:
                self.options.append((self.current, self.label))
            self.current = None
        elif tag == "script":
            self.in_script = False

    def client_dataset(self, symbol: str, digest: str) -> str | None:
        """Read bounded pinned Next JSON metadata for a nondefault asset.

        Initial SSR options contain BTC only. ETH lives in the serialized client
        props until the user changes the asset. Decode JSON, never JavaScript.
        This does not claim physical browser/hydration acceptance.
        """
        if sum(len(item) for item in self.scripts) > 2 * 1024 * 1024:
            raise RuntimeError("Bounded client metadata required")
        chunks = []
        for script in self.scripts:
            match = re.fullmatch(r"self\.__next_f\.push\((\[.*\])\);?", script.strip(), re.DOTALL)
            if match:
                message = json.loads(match.group(1))
                if (isinstance(message, list) and len(message) == 2
                        and message[0] == 1 and isinstance(message[1], str)):
                    chunks.append(message[1])
        text = "".join(chunks)
        decoder = json.JSONDecoder()
        offsets = list(re.finditer(r"\{", text))
        if len(offsets) > 10000:
            raise RuntimeError("Bounded client records required")
        for offset in offsets:
            try:
                item, _ = decoder.raw_decode(text, offset.start())
            except json.JSONDecodeError:
                continue
            if (isinstance(item, dict) and item.get("symbol") == symbol
                    and item.get("data_digest") == digest and item.get("timeframe") == "4h"
                    and item.get("purpose") == "research" and item.get("synthetic") is False
                    and isinstance(item.get("source"), dict) and item["source"].get("venue") == "bitget"
                    and isinstance(item.get("id"), str)
                    and re.fullmatch(r"[0-9a-f-]{36}", item["id"])):
                return item["id"]
        return None


class DevelopmentConnection(http.client.HTTPSConnection):
    def connect(self):
        allowed = {urlsplit(APP).hostname, urlsplit(IDP).hostname}
        expected_port = 443 if PUBLIC_PREVIEW else 8443
        if self.host not in allowed or self.port != expected_port or self._tunnel_host:
            raise RuntimeError("Only the selected development names/port are allowed")
        if PUBLIC_PREVIEW:
            # Exercise actual public DNS and certificate-chain/hostname checks.
            # Never substitute loopback or the development CA in this mode.
            return super().connect()
        raw = socket.create_connection(("127.0.0.1", 8443), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class DevelopmentTLS(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(DevelopmentConnection, req, context=CONTEXT)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def client():
    if CONTEXT is None or not CONTEXT.check_hostname or CONTEXT.verify_mode != ssl.CERT_REQUIRED:
        raise RuntimeError("Verified development TLS configuration required")
    return build_opener(ProxyHandler({}), DevelopmentTLS(context=CONTEXT),
                        HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())


def request(opener, path: str, *, data=None, raw: bytes | None = None, headers=None):
    if not path.startswith((APP + "/", IDP + "/")):
        raise RuntimeError("Unexpected request origin")
    options = dict(headers or {})
    if data is not None:
        raw = json.dumps(data).encode()
        options["Content-Type"] = "application/json"
    if raw is not None:
        parts = urlsplit(path)
        options.setdefault("Origin", f"{parts.scheme}://{parts.netloc}")
    try:
        response = opener.open(Request(path, data=raw, headers=options), timeout=10)
    except HTTPError as response:
        return response.code, response.headers, response.read()
    with response:
        return response.status, response.headers, response.read()


def totp() -> str:
    output = (LOCAL / "pilot-totp.txt").read_text()
    found = re.search(r"otpauth://[^\s]+", output)
    if not found:
        raise RuntimeError("Protected test factor has no URI")
    uri = found.group(0).rstrip("'\"")
    params = parse_qs(urlsplit(uri).query)
    value = params["secret"][0]
    key = base64.b32decode(value + "=" * (-len(value) % 8))
    period = int(params.get("period", ["30"])[0])
    digits = int(params.get("digits", ["6"])[0])
    algorithm = params.get("algorithm", ["SHA1"])[0].lower()
    counter = struct.pack(">Q", int(time.time()) // period)
    digest = hmac.new(key, counter, algorithm).digest()
    offset = digest[-1] & 15
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff
    return str(number % (10 ** digits)).zfill(digits)


def check(condition: bool, label: str):
    if not condition:
        raise RuntimeError(label)
    print("PASS", label)


def main() -> None:
    global STEP, APP, IDP, CONTEXT, PUBLIC_PREVIEW
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-preview", action="store_true",
                        help="Use the explicitly approved public development domains with system-trusted TLS.")
    parser.add_argument("--snapshot-file", type=Path,
                        default=LOCAL / "research-data/btc-research.json")
    args = parser.parse_args()
    PUBLIC_PREVIEW = args.public_preview
    if PUBLIC_PREVIEW:
        APP = "https://cockpit.investalo.de"
        IDP = "https://auth.cockpit.investalo.de"
        CONTEXT = ssl.create_default_context()
        identity = json.loads((LOCAL / "public-preview-identity.json").read_text())
        if (not isinstance(identity, dict)
                or identity.get("username") != "pilot"
                or identity.get("issuer") != IDP
                or identity.get("tenant_name") != "Lokale Entwicklung"
                or not isinstance(identity.get("subject"), str)
                or not re.fullmatch(
                    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                    identity["subject"],
                )):
            raise RuntimeError("Expected a deliberately provisioned public development identity")
    else:
        APP = "https://cockpit.local.test:8443"
        IDP = "https://auth.cockpit.local.test:8443"
        CONTEXT = ssl.create_default_context(cafile=str(LOCAL / "local_ca_cert"))
    with args.snapshot_file.open("rb") as stream:
        snapshot_bytes = stream.read(16 * 1024 * 1024 + 1)
    if len(snapshot_bytes) > 16 * 1024 * 1024:
        raise RuntimeError("Public research test snapshot exceeds size bound")
    snapshot = json.loads(snapshot_bytes)
    expected_digest = snapshot.get("data_digest")
    if (snapshot.get("schema_version") != "marketdata-snapshot/1"
            or snapshot.get("symbol") not in ("BTC/USDT", "ETH/USDT") or snapshot.get("synthetic") is not False
            or snapshot.get("source", {}).get("venue") != "bitget"
            or not isinstance(expected_digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", expected_digest)):
        raise RuntimeError("Expected a real public crypto research snapshot")
    expected_symbol = snapshot["symbol"]
    password = re.search(r"(?m)^Password: (\S+)",
                         (LOCAL / "pilot-access.txt").read_text()).group(1)
    opener = client()
    STEP = "public UI and security headers"
    status, headers, body = request(opener, APP + "/")
    check(status == 200 and b'href="/api/auth/login"' in body, "unauthenticated login page")
    csp = headers.get("Content-Security-Policy", "")
    nonce = re.search(r"'nonce-([^']+)'", csp)
    check(bool(nonce) and "'unsafe-inline'" not in csp.split("style-src")[0],
          "script CSP uses a nonce")
    check(bool(nonce) and f'nonce="{nonce.group(1)}"'.encode() in body,
          "HTML script nonce matches CSP")
    check(headers.get("Cache-Control", "").find("no-store") >= 0,
          "private pages are not cached")
    status, _, _ = request(opener, APP + "/api/backtests",
                           data={"symbol": "BTC/USDT", "timeframe": "4h"})
    check(status == 401, "unauthenticated mutation rejected")
    STEP = "OIDC login initiation"
    status, headers, _ = request(opener, APP + "/api/auth/login")
    authorization = headers.get("Location", "")
    params = parse_qs(urlsplit(authorization).query)
    check(status in (302, 303, 307) and authorization.startswith(IDP + "/"),
          "login reaches trusted HTTPS issuer")
    check(params.get("code_challenge_method") == ["S256"], "OIDC uses PKCE S256")
    check(params.get("prompt") == ["login"], "OIDC requests fresh login")
    cookies = headers.get_all("Set-Cookie") or []
    check(any("secure" in value.lower() and "httponly" in value.lower() and "samesite=lax" in value.lower()
              for value in cookies), "login binding cookie is secure and HttpOnly")
    # Initialize the provider session, then use its documented native factor API.
    _, initial_headers, _ = request(opener, authorization)
    flow_id = parse_qs(urlsplit(initial_headers.get("Location", "")).query).get("flow_id", [None])[0]
    if not flow_id:
        raise RuntimeError("Provider did not initialize an OIDC flow")
    factor_flow = {"flow": "openid_connect", "flowID": flow_id}
    STEP = "first factor"
    status, _, factor_body = request(opener, IDP + "/api/firstfactor", data={
        "username": "pilot", "password": password, "keepMeLoggedIn": False,
        "targetURL": authorization, "requestMethod": "GET", **factor_flow,
    })
    check(status == 200 and json.loads(factor_body).get("status") == "OK",
          "local test password accepted")
    status, _, body = request(opener, APP + "/")
    check(status == 200 and b'href="/api/auth/login"' in body,
          "password alone grants no application access")
    STEP = "second factor"
    status, _, factor_body = request(opener, IDP + "/api/secondfactor/totp", data={
        "token": "not-a-totp", "targetURL": authorization, "requestMethod": "GET", **factor_flow,
    })
    check(status >= 400, "invalid second factor rejected")
    status, _, factor_body = request(opener, IDP + "/api/secondfactor/totp", data={
        "token": totp(), "targetURL": authorization, "requestMethod": "GET", **factor_flow,
    })
    check(status == 200 and json.loads(factor_body).get("status") == "OK",
          "valid local TOTP accepted")
    STEP = "OIDC authorization/consent"
    # Keep the original provider flow. Starting another authorization request
    # with prompt=login would correctly demand fresh authentication again.
    location = IDP + "/consent/openid/decision?flow=openid_connect&flow_id=" + flow_id
    # Explicit first-party consent is handled by the provider, never forged
    # as an application token. Its test consent uses exactly this browser flow.
    if location.startswith(IDP + "/consent"):
        consent_id = parse_qs(urlsplit(location).query).get("flow_id", [None])[0]
        if consent_id is None:
            raise RuntimeError("Provider consent identifier missing")
        status, _, metadata = request(opener, IDP + "/api/oidc/consent?flow_id=" + consent_id)
        if status != 200:
            raise RuntimeError("Provider consent metadata refused test request")
        consent = json.loads(metadata)["data"]
        check(not consent.get("require_login"), "provider verifies fresh authentication")
        check(consent["client_id"] == "investalo-cockpit",
              "provider consent belongs to this client")
        claims = list(dict.fromkeys((consent.get("claims") or []) +
                                    (consent.get("essential_claims") or [])))
        status, _, body = request(opener, IDP + "/api/oidc/consent", data={
            "flow_id": consent_id, "client_id": "investalo-cockpit",
            "consent": True, "pre_configure": False, "claims": claims,
        })
        if status != 200:
            raise RuntimeError("Provider consent endpoint refused test request")
        reply = json.loads(body)
        check(reply.get("status") == "OK", "provider accepts explicit consent")
        continuation = reply["data"]["redirect_uri"]
        status, headers, body = request(opener, continuation)
        location = headers.get("Location", "")
    check(status in (302, 303) and location.startswith(APP + "/api/auth/callback"),
          "two factors grant an application callback")
    STEP = "BFF callback"
    status, headers, _ = request(opener, location)
    check(status in (302, 303, 307) and headers.get("Location") == APP + "/",
          "BFF verifies token and tenant membership")
    cookies = headers.get_all("Set-Cookie") or []
    check(any("__Host-" in value and "Secure" in value and "HttpOnly" in value
              for value in cookies), "opaque application session cookie")
    status, _, body = request(opener, APP + "/")
    check(status == 200 and b"API verbunden" in body, "authenticated cockpit reads tenant API")
    status, _, datasets_page = request(opener, APP + "/backtests")
    dataset_options = DatasetOptions()
    dataset_options.feed(datasets_page.decode())
    dataset_id = next((value for value, label in dataset_options.options
                       if re.fullmatch(r"[0-9a-f-]{36}", value)
                       and label.startswith("Bitget")
                       and expected_digest[:10] in label), None)
    if not dataset_id:
        dataset_id = dataset_options.client_dataset(expected_symbol, expected_digest)
    if not dataset_id:
        raise RuntimeError("Expected imported public research snapshot missing")
    check(status == 200, "authenticated cockpit lists imported public research data")
    status, _, _ = request(opener, location)
    check(status == 401, "authorization callback cannot be replayed")
    STEP = "CSRF and logout"
    status, _, _ = request(opener, APP + "/api/backtests",
                           data={"symbol": "BTC/USDT", "timeframe": "4h"})
    check(status in (400, 403), "authenticated mutation without CSRF rejected")
    csrf = re.search(rb'name="csrf"[^>]*value="([^"]+)"', body)
    if not csrf:
        raise RuntimeError("Logout CSRF missing from authenticated page")
    STEP = "credential metadata and unavailable fresh factor"
    status, credential_headers, credential_page = request(opener, APP + "/security/credentials")
    check(status == 200 and "Bestätigungsschritt bleibt gesperrt".encode() in credential_page,
          "credential page honestly displays the unavailable fresh factor")
    check("no-store" in credential_headers.get("Cache-Control", ""),
          "credential metadata page is not cached")
    credential_payload = {"platform_account_id": str(uuid4()), "action": "register"}
    status, _, _ = request(opener, APP + "/api/credentials/step-up", data=credential_payload)
    check(status == 400, "credential initiation without CSRF rejected")
    credential_headers = {"X-CSRF-Token": csrf.group(1).decode()}
    status, blocked_headers, result = request(opener, APP + "/api/credentials/step-up",
                                             data=credential_payload, headers=credential_headers)
    check(status == 503 and b"authorization_url" not in result and "no-store" in blocked_headers.get("Cache-Control", ""),
          "credential step-up cannot redirect or grant without fresh factor proof")
    status, _, result = request(opener, APP + "/api/credentials/confirm",
                                data={"confirmed": True, "confirmation_token": "a" * 43},
                                headers=credential_headers)
    check(status == 503 and b"verified" not in result,
          "credential confirmation cannot claim successful fresh MFA")
    status, _, _ = request(opener, APP + "/api/credentials/confirm",
                           data={"confirmed": True}, headers=credential_headers)
    check(status == 400, "confirmation without the displayed grant token rejected")
    STEP = "passkey enrollment HTTP boundary"
    status, passkey_headers, passkey_page = request(opener, APP + "/security/passkeys")
    check(status == 200 and b'id="passkey-ticket"' in passkey_page,
          "authenticated passkey page offers administrative invitation enrollment")
    check("no-store" in passkey_headers.get("Cache-Control", ""),
          "passkey status page is not cached")
    enrollment = {"token": base64.urlsafe_b64encode(hashlib.sha256(uuid4().bytes).digest()).rstrip(b"=").decode()}
    start_path = APP + "/api/passkeys/enrollment/start"
    finish_path = APP + "/api/passkeys/enrollment/finish"
    status, _, _ = request(opener, start_path, data=enrollment)
    check(status == 400, "passkey enrollment without CSRF rejected")
    status, _, result = request(opener, start_path, data=enrollment, headers=credential_headers)
    check(status == 400 and b"options" not in result and b"attempt_id" not in result,
          "unissued invitation creates no browser challenge")
    status, _, _ = request(opener, start_path, data=enrollment,
                           headers={**credential_headers, "Origin": "https://foreign.invalid"})
    check(status == 400, "passkey enrollment from another origin rejected")
    status, _, _ = request(opener, start_path,
                           raw=b'{"token":"' + enrollment["token"].encode() + b'","token":"duplicate"}',
                           headers={**credential_headers, "Content-Type": "application/json"})
    check(status == 400, "duplicate enrollment fields rejected")
    status, _, result = request(opener, finish_path, data={
        "attempt_id": enrollment["token"], "credential": {},
    }, headers=credential_headers)
    check(status == 400 and b"registered" not in result,
          "unstarted enrollment cannot persist a credential")
    status, _, _ = request(client(), start_path, data=enrollment)
    check(status == 401, "unauthenticated enrollment rejected")
    STEP = "BFF job acceptance and idempotency"
    job_headers = {"X-CSRF-Token": csrf.group(1).decode(),
                   "Idempotency-Key": str(uuid4())}
    job_payload = {"symbol": expected_symbol, "timeframe": "4h",
                   "dataset_id": dataset_id}
    status, _, result = request(opener, APP + "/api/backtests",
                                data=job_payload, headers=job_headers)
    job = json.loads(result)
    check(status == 202 and job.get("status") == "QUEUED" and bool(job.get("id")),
          "authenticated BFF queues a real persisted job")
    status, _, result = request(opener, APP + "/api/backtests",
                                data=job_payload, headers=job_headers)
    check(status == 202 and json.loads(result).get("id") == job["id"],
          "same idempotency key returns the same job")
    status, _, _ = request(opener, APP + "/api/backtests",
                           data={"symbol": "ETH/USDT" if expected_symbol == "BTC/USDT" else "BTC/USDT", "timeframe": "4h"},
                           headers=job_headers)
    check(status == 409, "idempotency key cannot switch the requested asset")
    STEP = "actual research worker result"
    deadline = time.monotonic() + 120
    result_page = b""
    while time.monotonic() < deadline:
        status, _, result_page = request(opener, APP + "/backtests/" + job["id"])
        if b"NICHT VALIDIERT" in result_page:
            break
        if "Kein bestätigtes Ergebnis".encode() in result_page:
            raise RuntimeError("Actual worker failed the public research job")
        time.sleep(1)
    check(status == 200 and b"NICHT VALIDIERT" in result_page,
          "actual offline worker publishes a tenant-bound research result")
    check(b"Netto-PnL" in result_page and b'class="equity-chart"' in result_page,
          "cockpit renders actual net metrics and an equity curve")
    check(expected_digest.encode() in result_page,
          "displayed result retains the frozen public data digest")
    STEP = "logout"
    from urllib.parse import urlencode
    status, _, _ = request(
        opener, APP + "/api/auth/logout",
        raw=urlencode({"csrf": csrf.group(1).decode()}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    check(status in (302, 303), "explicit logout succeeds")
    status, _, body = request(opener, APP + "/")
    check(status == 200 and b'href="/api/auth/login"' in body,
          "logged-out browser loses application access")
    STEP = "fresh login with existing IdP session"
    _, headers, _ = request(opener, APP + "/api/auth/login")
    _, headers, _ = request(opener, headers.get("Location", ""))
    existing_flow = parse_qs(urlsplit(headers.get("Location", "")).query).get("flow_id", [None])[0]
    if not existing_flow:
        raise RuntimeError("Provider did not initialize fresh login flow")
    status, _, result = request(opener, IDP + "/api/oidc/consent?flow_id=" + existing_flow)
    check(status == 200 and json.loads(result).get("data", {}).get("require_login") is True,
          "existing IdP session cannot bypass fresh application login")
    STEP = "provider factor freshness limitation"
    # The provider's dedicated reauthentication endpoint preserves MFA;
    # ordinary /firstfactor instead resets the session and would test login.
    # Its request time has fractions but authentication timestamps have whole
    # seconds. Cross that boundary so prompt=login does not obscure this check.
    time.sleep(1.05)
    status, _, result = request(opener, IDP + "/api/firstfactor/reauthenticate", data={
        "password": password,
        "flow": "openid_connect", "flowID": existing_flow,
    })
    check(status == 200 and json.loads(result).get("status") == "OK",
          "existing MFA session accepts password reauthentication")
    status, _, result = request(opener, IDP + "/api/oidc/consent?flow_id=" + existing_flow)
    check(status == 200 and json.loads(result).get("data", {}).get("require_login") is False,
          "provider can reuse the old second factor, requiring a separate action proof")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Exceptions/HTTP errors may contain sensitive query strings. Do not echo.
        print(f"FAIL development integration step: {STEP}; no sensitive output emitted.",
              file=sys.stderr)
        print("Error class:", type(error).__name__, file=sys.stderr)
        if type(error) is RuntimeError:
            print("Reason:", str(error), file=sys.stderr)
        sys.exit(1)
