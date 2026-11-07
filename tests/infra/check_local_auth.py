#!/usr/bin/env python3
"""Exercise the real local TLS/IdP/BFF boundary using only generated test data.

No production names, outbound network, token/password output or disabled TLS.
Run after bootstrap-local, migration and provision-local-test.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
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
CONTEXT = ssl.create_default_context(cafile=str(LOCAL / "local_ca_cert"))
STEP = "initialize"


class LocalConnection(http.client.HTTPSConnection):
    def connect(self):
        if self.host not in {"cockpit.local.test", "auth.cockpit.local.test"} or self.port != 8443:
            raise RuntimeError("Only local test names/port are allowed")
        raw = socket.create_connection(("127.0.0.1", 8443), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class LocalTLS(HTTPSHandler):
    def https_open(self, req):
        return self.do_open(LocalConnection, req, context=CONTEXT)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def client():
    return build_opener(ProxyHandler({}), LocalTLS(context=CONTEXT),
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
    global STEP
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
    status, _, _ = request(opener, location)
    check(status == 401, "authorization callback cannot be replayed")
    STEP = "CSRF and logout"
    status, _, _ = request(opener, APP + "/api/backtests",
                           data={"symbol": "BTC/USDT", "timeframe": "4h"})
    check(status in (400, 403), "authenticated mutation without CSRF rejected")
    csrf = re.search(rb'name="csrf"[^>]*value="([^"]+)"', body)
    if not csrf:
        raise RuntimeError("Logout CSRF missing from authenticated page")
    STEP = "BFF job acceptance and idempotency"
    job_headers = {"X-CSRF-Token": csrf.group(1).decode(),
                   "Idempotency-Key": str(uuid4())}
    job_payload = {"symbol": "BTC/USDT", "timeframe": "4h"}
    status, _, result = request(opener, APP + "/api/backtests",
                                data=job_payload, headers=job_headers)
    job = json.loads(result)
    check(status == 202 and job.get("status") == "queued" and bool(job.get("id")),
          "authenticated BFF queues a real persisted job")
    status, _, result = request(opener, APP + "/api/backtests",
                                data=job_payload, headers=job_headers)
    check(status == 202 and json.loads(result).get("id") == job["id"],
          "same idempotency key returns the same job")
    status, _, _ = request(opener, APP + "/api/backtests",
                           data={"symbol": "ETH/USDT", "timeframe": "4h"},
                           headers=job_headers)
    check(status == 409, "idempotency key cannot switch the requested asset")
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


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Exceptions/HTTP errors may contain sensitive query strings. Do not echo.
        print(f"FAIL local integration step: {STEP}; no sensitive output emitted.",
              file=sys.stderr)
        print("Error class:", type(error).__name__, file=sys.stderr)
        if type(error) is RuntimeError:
            print("Reason:", str(error), file=sys.stderr)
        sys.exit(1)
